"""
Expressions for building excel formulas without having to use concrete positions.
"""
import operator
import re


class Expression(object):
    """
    Base class for all worksheet expressions.

    Expressions are used to build formulas referencing ranges in the
    worksheet by labels which are resolved to cell references when the
    worksheet is written out.

    Expressions may be combined using binary operators.
    """
    def __init__(self, value=None):
        if value is not None:
            self.value = value

    def __add__(self, other):
        return BinOp(self, _make_expr(other), "+")

    def __sub__(self, other):
        return BinOp(self, _make_expr(other), "-")

    def __mul__(self, other):
        return BinOp(self, _make_expr(other), "*")

    def __truediv__(self, other):
        return BinOp(self, _make_expr(other), "/")

    def __lt__(self, other):
        return BinOp(self, _make_expr(other), "<")

    def __le__(self, other):
        return BinOp(self, _make_expr(other), "<=")

    def __eq__(self, other):
        return BinOp(self, _make_expr(other), "=")

    def __ne__(self, other):
        return BinOp(self, _make_expr(other), "<>")

    def __gt__(self, other):
        return BinOp(self, _make_expr(other), ">")

    def __ge__(self, other):
        return BinOp(self, _make_expr(other), ">=")

    def __and__(self, other):
        return BinOp(self, _make_expr(other), "&")

    def get_formula(self, workbook, row, col):
        return "=%s" % self._strip(self.resolve(workbook, row, col))

    @property
    def value(self):
        """Set a calculated value for this Expression.
        Used when writing formulas using XlsxWriter to give cells
        an initial value when the sheet is loaded without being calculated.
        """
        try:
            if isinstance(self.__value, Expression):
                return self.__value.value
            return self.__value
        except AttributeError:
            return 0

    @property
    def has_value(self):
        """return True if value has been set"""
        try:
            if isinstance(self.__value, Expression):
                return self.__value.has_value
            return True
        except AttributeError:
            return False

    @value.setter
    def value(self, value):
        self.__value = value

    @staticmethod
    def _strip(x):
        # strip off the outer parentheses if they match
        return re.sub("^\((.*)\)$", r"\1", x)

    def resolve(self, workbook, worksheet, col, row):
        raise NotImplementedError("Expression.resolve")


class Cell(Expression):
    """
    Reference to a cell in a table.

    :param col: Column label this refers to.
    :param row: Row label this refers to, or None to use the current row.
    :param row_offset: Offset from the row, used when resolving.
    :param table: Name of table the column is in, if not in the same table this expression is in. 
                  Use "%s!%s" % (worksheet.name, table.name) if refering to a table in another worksheet
    :param col_fixed: If True when converted to an address the column will be fixed.
    :param row_fixed: If True when converted to an address the row will be fixed.
    """
    def __init__(self, col, row=None, row_offset=0, table=None, col_fixed=None, row_fixed=None, **kwargs):
        super(Cell, self).__init__(**kwargs)
        self.__col = col
        self.__row = row
        self.__row_offset = row_offset
        self.__table = table
        self.__col_fixed = col_fixed
        self.__row_fixed = row_fixed

    def resolve(self, workbook, row, col):
        table, worksheet = workbook.get_table(self.__table)
        top, left = worksheet.get_table_pos(table.name)
        col_offset = table.get_column_offset(self.__col)

        # if the row has been given use fixed references in the formula unless they've been set explicitly
        if self.__row is not None:
            row = table.get_row_offset(self.__row)
            row_fixed = self.__row_fixed if self.__row_fixed is not None else True
            col_fixed = self.__col_fixed if self.__col_fixed is not None else True
        else:
            # otherwise use un-fixed addresses, unless set explicitly
            row_fixed = self.__row_fixed if self.__row_fixed is not None else False
            col_fixed = self.__col_fixed if self.__col_fixed is not None else False

        return _to_addr(worksheet.name,
                        top + row + self.__row_offset,
                        left + col_offset,
                        row_fixed=row_fixed,
                        col_fixed=col_fixed)

    
class Column(Expression):
    """
    Reference to a column in a table.

    :param col: Column label this refers to.
    :param include_header: True if this expression should include the column header.
    :param table: Name of table the column is in, if not in the same table this expression is in.
                  Use "%s!%s" % (worksheet.name, table.name) if refering to a table in another worksheet
    :param col_fixed: If True when converted to an address the column will be fixed.
    :param row_fixed: If True when converted to an address the row will be fixed.
    """
    def __init__(self, col, include_header=False, table=None, col_fixed=True, row_fixed=True, **kwargs):
        super(Column, self).__init__(**kwargs)
        self.__col = col
        self.__include_header = include_header
        self.__table = table
        self.__col_fixed = col_fixed
        self.__row_fixed = row_fixed

    def resolve(self, workbook, row, col):
        table, worksheet = workbook.get_table(self.__table)
        top, left = worksheet.get_table_pos(table.name)
        col_offset = table.get_column_offset(self.__col)
        row_offset = 0 if self.__include_header else table.header_height 
        return "'%s'!%s:%s" % (
                    worksheet.name,
                    _to_addr(None, top + row_offset, left + col_offset,
                             row_fixed=self.__row_fixed,
                             col_fixed=self.__col_fixed),
                    _to_addr(None, top + table.height - 1, left + col_offset,
                             row_fixed=self.__row_fixed,
                             col_fixed=self.__col_fixed))


class Index(Expression):
    """
    Reference to a table's index.

    :param include_header: True if this expression should include the index header.
    :param table: Name of table that owns the index, if not the table this expression is in.
                  Use "%s!%s" % (worksheet.name, table.name) if refering to a table in another worksheet
    :param col_fixed: If True when converted to an address the column will be fixed.
    :param row_fixed: If True when converted to an address the row will be fixed.
    """
    def __init__(self, include_header=False, table=None, col_fixed=True, row_fixed=True, **kwargs):
        super(Index, self).__init__(**kwargs)
        self.__include_header = include_header
        self.__table = table
        self.__col_fixed = col_fixed
        self.__row_fixed = row_fixed

    def resolve(self, workbook, row, col):
        table, worksheet = workbook.get_table(self.__table)
        top, left = worksheet.get_table_pos(table.name)
        col_offset = table.get_index_offset()
        row_offset = 0 if self.__include_header else table.header_height
        return "'%s'!%s:%s" % (
                    worksheet.name,
                    _to_addr(None, top + row_offset, left + col_offset,
                             row_fixed=self.__row_fixed,
                             col_fixed=self.__col_fixed),
                    _to_addr(None, top + table.height - 1, left + col_offset,
                             row_fixed=self.__row_fixed,
                             col_fixed=self.__col_fixed))


class Range(Expression):
    """
    Reference to a range in a table.

    :param left_col: Left most column label this refers to.
    :param right_col: Right most column label this refers to.
    :param top_row: Top most row label, or None to select from the top of the table.
    :param bottom_row: Bottom most row label, or None to select to the bottom of the table, or False to select single row
    :param include_header: Include table header in the range.
    :param table: Name of table the column is in, if not in the same table this expression is in.
                  Use "%s!%s" % (worksheet.name, table.name) if refering to a table in another worksheet
    :param col_fixed: If True when converted to an address the column will be fixed.
    :param row_fixed: If True when converted to an address the row will be fixed.
    """
    def __init__(self,
                 left_col,
                 right_col,
                 top_row=None,
                 bottom_row=None,
                 include_header=True,
                 table=None,
                 col_fixed=True,
                 row_fixed=True,
                 **kwargs):
        super(Range, self).__init__(**kwargs)
        self.__left_col = left_col
        self.__right_col = right_col
        self.__top = top_row
        self.__bottom = bottom_row
        self.__include_header = include_header
        self.__table = table
        self.__col_fixed = col_fixed
        self.__row_fixed = row_fixed

    def resolve(self, workbook, row, col):
        table, worksheet = workbook.get_table(self.__table)
        top, left = worksheet.get_table_pos(table.name)
        left_col_offset = table.get_column_offset(self.__left_col)
        right_col_offset = table.get_column_offset(self.__right_col)
        
        if self.__top is None:
            top_row_offset = 0 if self.__include_header else table.header_height
        else:
            top_row_offset = table.get_row_offset(self.__top)

        if self.__bottom is None:
            bottom_row_offset = table.height - 1
        elif self.__bottom is False:
            bottom_row_offset = top_row_offset
        else:
            bottom_row_offset = table.get_row_offset(self.__bottom)

        return "'%s'!%s:%s" % (
                    worksheet.name,
                    _to_addr(None, top + top_row_offset, left + left_col_offset,
                             row_fixed=self.__row_fixed,
                             col_fixed=self.__col_fixed),
                    _to_addr(None, top + bottom_row_offset, left + right_col_offset,
                             row_fixed=self.__row_fixed,
                             col_fixed=self.__col_fixed))


class Formula(Expression):
    """
    Formula expression.

    E.g. to create a formula like "=SUMPRODUCT(a, b)" where a and b
    are columns in a table you would do::

        formula = Formula("SUMPRODUCT", Column("col_a"), Column("col_b"))

    :param name: Name of Excel function, eg "SUMPRODUCT".
    :param args: Expressions to use as arguments to the function.
    """
    def __init__(self, name, *args, **kwargs):
        super(Formula, self).__init__(**kwargs)
        self.__name = name
        self.__args = args

    def resolve(self, workbook, row, col):
        def to_arg(x):
            if x is None:
                return ""
            return self._strip(_make_expr(x).resolve(workbook, row, col))
        args = [to_arg(x) for x in self.__args]
        return "%s(%s)" % (self.__name, ",".join(args))
    
    
class ArrayExpression(Expression):
    """
    Wraps an expression in an array formula (ie. surrounds it with {})
    
    :param xltable.Expression expr: Expression to be wrapped
    """

    def __init__(self, expr):
        Expression.__init__(self, expr)
        self.__expr = expr

    def resolve(self, workbook, row, col):
        return self.__expr.resolve(workbook, row, col)

    def get_formula(self, workbook, row, col):
        return "{%s}" % self.__expr.get_formula(workbook, row, col).strip("{}")


class BinOp(Expression):
    """
    Internal use - composite expression combining two expression with a binary operator.
    """
    __operators = {
        "+": operator.add,
        "-": operator.sub,
        "*": operator.mul,
        "/": operator.truediv,
        ">": operator.gt,
        "<": operator.lt,
        "<=": operator.le,
        ">=": operator.ge,
        "!=": operator.ne,
        "=": operator.eq,
        "&": operator.and_,
        "|": operator.or_,
    }

    def __init__(self, lhs, rhs, op, **kwargs):
        super(BinOp, self).__init__(**kwargs)
        self.__lhs = lhs
        self.__rhs = rhs
        self.__op = op
        if lhs.has_value and rhs.has_value:
            self.value = self.__operators[op](lhs.value, rhs.value)

    def resolve(self, workbook, row, col):
        return "(%s%s%s)" % (
            self.__lhs.resolve(workbook, row, col),
            self.__op,
            self.__rhs.resolve(workbook, row, col))


class ConstExpr(Expression):
    """
    Internal use - expression for wrapping constants.
    """
    def __init__(self, value, **kwargs):
        super(ConstExpr, self).__init__(**kwargs)
        self.value = value
        self.__value = value
        
    def resolve(self, workbook, row, col):
        if isinstance(self.__value, str):
            return '"%s"' % self.__value
        if isinstance(self.__value, bool):
            return "TRUE" if self.__value else "FALSE"
        return str(self.__value)


class ArrayConstant(Expression):
    """
    An evaluated array, an "Array Constant". Can increase performance and/or
    reduce dependencies
    """
    def __init__(self, array, **kwargs):
        super(ArrayConstant, self).__init__(**kwargs)
        self.value = array
        self.__value = array

    def resolve(self, workbook, row, col):
        arr_str = ";".join(",".join(map(str,row)) for row in self.__value)
        return "{%s}" % arr_str


def _to_addr(worksheet, row, col, row_fixed=False, col_fixed=False):
    """converts a (0,0) based coordinate to an excel address"""
    addr = ""
    A = ord('A')
    col += 1
    while col > 0:
        addr = chr(A + ((col - 1) % 26)) + addr
        col = (col - 1) // 26

    prefix = ("'%s'!" % worksheet) if worksheet else ""
    col_modifier = "$" if col_fixed else ""
    row_modifier = "$" if row_fixed else ""
    return prefix + "%s%s%s%d" % (col_modifier, addr, row_modifier, row+1)


def _make_expr(x):
    if isinstance(x, Expression):
        return x
    return ConstExpr(x)
