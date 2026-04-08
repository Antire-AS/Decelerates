import ExcelJS from "exceljs";

/**
 * Download a list of row objects as an .xlsx file.
 *
 * Plan §🔴 #3: we swapped from `xlsx` (SheetJS) to `exceljs` after Dependabot
 * flagged 2 high-severity advisories against the npm-distributed xlsx package
 * — SheetJS moved off npm after a supply-chain incident and never publishes
 * fixes there, so the npm package is permanently stuck on the vulnerable
 * 0.18.5. exceljs is actively maintained with no current advisories.
 *
 * Signature is backward-compatible: the 2 call sites don't change.
 */
export async function downloadXlsx(
  rows: Record<string, unknown>[],
  filename: string,
): Promise<void> {
  if (!rows.length) return;

  const workbook = new ExcelJS.Workbook();
  const sheet = workbook.addWorksheet("Data");

  // Derive the column list from the first row — mirrors json_to_sheet's
  // auto-header behaviour. Callers already pass uniform dicts so this is safe.
  const headers = Object.keys(rows[0]);
  sheet.columns = headers.map((h) => ({ header: h, key: h }));
  sheet.addRows(rows);

  // exceljs writes to a buffer; we wrap it in a Blob and trigger a browser
  // download via an anchor tag. Works in all modern browsers.
  const buffer = await workbook.xlsx.writeBuffer();
  const blob = new Blob([buffer], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename.endsWith(".xlsx") ? filename : `${filename}.xlsx`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
