// Google Apps Script, bound to the tracker spreadsheet.
//
// Receives a POST from an ntfy notification action button — {url, column, value[, secret]} —
// finds the row whose Link column (D) matches `url`, and writes `value` into `column` (E or F).
// This is the "server" side of the phone approval flow: ntfy can't call back into a machine on
// your desk, so a Web App deployment of this script (hosted free by Google) is what receives the
// tap instead. See README.md "Phone approval" for deployment steps.

const SHEET_NAME = "Internship & Job Tracker";
const LINK_COLUMN = 4; // D
const SECRET = ""; // optional: set to match APPROVAL_WEBHOOK_SECRET in .env

function doPost(e) {
  const body = JSON.parse(e.postData.contents);

  if (SECRET && body.secret !== SECRET) {
    return ContentService.createTextOutput("forbidden");
  }

  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAME);
  const links = sheet.getRange(1, LINK_COLUMN, sheet.getLastRow(), 1).getValues();
  const row = links.findIndex(([link]) => link === body.url) + 1;

  if (row < 1) {
    return ContentService.createTextOutput("not found");
  }

  sheet.getRange(row, columnLetterToIndex(body.column)).setValue(body.value);
  return ContentService.createTextOutput("ok");
}

function columnLetterToIndex(letter) {
  return letter.toUpperCase().charCodeAt(0) - 64; // "A" -> 1, "E" -> 5, "F" -> 6
}
