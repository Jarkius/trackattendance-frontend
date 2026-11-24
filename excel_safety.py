"""Keep user-supplied text from becoming live formulas in exported workbooks."""

from openpyxl.workbook.workbook import Workbook


def neutralize_formulas(workbook: Workbook) -> int:
    """Store every formula cell as plain text. Returns how many were changed.

    openpyxl writes any string that starts with "=" as a formula. Exports here
    contain typed walk-in names, badge values and roster text from other
    stations, none of which should ever run when an organiser opens the file.
    The exports themselves never write formulas, so this is safe to run on
    every workbook just before saving.
    """
    changed = 0
    for sheet in workbook.worksheets:
        for row in sheet.iter_rows():
            for cell in row:
                if cell.data_type == "f":
                    cell.data_type = "s"
                    changed += 1
    return changed
