// Google Apps Script, bound to the tracker spreadsheet.
//
// Receives a POST from an ntfy notification action button — {op, url, ...[, secret]} — and finds
// the row whose Link column (D) matches `url`. Two ops:
//
//   {op: "interest", url, column, value}  writes `value` into `column` (E or F) on that row
//   {op: "dismiss", url}                  moves that row to the Discarded tab
//
// A body with no `op` is treated as "interest", so buttons from notifications sent before the
// dismiss flow existed still work.
//
// This is the "server" side of the phone approval flow: ntfy can't call back into a machine on
// your desk, so a Web App deployment of this script (hosted free by Google) is what receives the
// tap instead. See README.md "Phone approval" for deployment steps.

const SHEET_NAME = "Internship & Job Tracker";
const DISCARD_SHEET_NAME = "Discarded";
const LINK_COLUMN = 4; // D
const LAST_COLUMN = 6; // F
const SECRET = ""; // optional: set to match APPROVAL_WEBHOOK_SECRET in .env

function doPost(e) {
  const body = JSON.parse(e.postData.contents);

  if (SECRET && body.secret !== SECRET) {
    return ContentService.createTextOutput("forbidden");
  }

  // A dismissal deletes a row, which shifts every row number below it, so two taps landing at
  // once must not interleave.
  const lock = LockService.getScriptLock();
  lock.waitLock(20 * 1000);
  try {
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAME);
    const links = sheet.getRange(1, LINK_COLUMN, sheet.getLastRow(), 1).getValues();
    const row = links.findIndex(([link]) => link === body.url) + 1;

    if (row < 1) {
      return ContentService.createTextOutput("not found");
    }

    if (body.op === "dismiss") {
      dismissRow(sheet, row);
    } else {
      sheet.getRange(row, columnLetterToIndex(body.column)).setValue(body.value);
    }
    return ContentService.createTextOutput("ok");
  } finally {
    lock.releaseLock();
  }
}

// Move the row to the Discarded tab (created on first use) rather than deleting it outright, so
// a mistaken tap is recoverable by cut-and-pasting the row back.
function dismissRow(sheet, row) {
  const values = sheet.getRange(row, 1, 1, LAST_COLUMN).getValues();
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  const discard =
    spreadsheet.getSheetByName(DISCARD_SHEET_NAME) || spreadsheet.insertSheet(DISCARD_SHEET_NAME);
  discard.getRange(discard.getLastRow() + 1, 1, 1, LAST_COLUMN).setValues(values);
  sheet.deleteRow(row);
}

function columnLetterToIndex(letter) {
  return letter.toUpperCase().charCodeAt(0) - 64; // "A" -> 1, "E" -> 5, "F" -> 6
}
