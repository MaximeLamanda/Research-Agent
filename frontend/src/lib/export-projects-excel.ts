import ExcelJS from "exceljs";
import { Project, Source } from "@/lib/api";
import { getCountryLabel } from "@/data/countries";
import {
  formatDate,
  formatCountry,
  formatDepartment,
  formatPeople,
  formatArticleDates,
  formatProjectStatus,
  resolveStatusKey,
} from "@/lib/project-formatters";

export function filterProjectsByCountry(projects: Project[], country: string): Project[] {
  return projects.filter((project) => (project.country || "FR") === country);
}

const COLORS = {
  titleBg: "FF1E3A5F",
  titleText: "FFFFFFFF",
  subtitleText: "FF64748B",
  headerBg: "FF334155",
  headerText: "FFFFFFFF",
  rowEven: "FFF8FAFC",
  rowOdd: "FFFFFFFF",
  border: "FFE2E8F0",
  accent: "FF3B82F6",
  muted: "FF64748B",
  status: {
    conception: { bg: "FFDBEAFE", text: "FF1D4ED8" },
    travaux: { bg: "FFFEF3C7", text: "FFB45309" },
    livraison: { bg: "FFD1FAE5", text: "FF047857" },
  } as Record<string, { bg: string; text: string }>,
};

const HEADERS = [
  "Project",
  "Company",
  "Why this lead?",
  "City",
  "Country",
  "Région",
  "Address",
  "Delivery",
  "Area (m²)",
  "Sector",
  "Status",
  "Contacts",
  "Article date",
  "Sources",
  "Pertinence",
] as const;

const COL = {
  project: 0,
  leadPitch: 2,
  area: 8,
  status: 10,
  articleDate: 12,
  sources: 13,
  pertinence: 14,
} as const;

const COLUMN_WIDTHS = [32, 24, 40, 18, 14, 22, 36, 14, 14, 16, 14, 36, 16, 52, 14];

function thinBorder(): Partial<ExcelJS.Borders> {
  const side: Partial<ExcelJS.Border> = { style: "thin", color: { argb: COLORS.border } };
  return { top: side, left: side, bottom: side, right: side };
}

function applyHeaderStyle(cell: ExcelJS.Cell) {
  cell.font = { bold: true, color: { argb: COLORS.headerText }, size: 11 };
  cell.fill = { type: "pattern", pattern: "solid", fgColor: { argb: COLORS.headerBg } };
  cell.alignment = { horizontal: "center", vertical: "middle", wrapText: true };
  cell.border = thinBorder();
}

function applyDataStyle(cell: ExcelJS.Cell, isEven: boolean) {
  cell.fill = {
    type: "pattern",
    pattern: "solid",
    fgColor: { argb: isEven ? COLORS.rowEven : COLORS.rowOdd },
  };
  cell.border = thinBorder();
  cell.alignment = { vertical: "top", wrapText: true };
}

function buildSourcesRichText(sources: Source[]): ExcelJS.CellRichTextValue {
  const richText: ExcelJS.RichText[] = [];

  sources.forEach((source, index) => {
    if (index > 0) {
      richText.push({ text: "\n" });
    }

    const title = source.title || "Untitled article";
    richText.push({
      font: { bold: true, size: 11, color: { argb: "FF0F172A" } },
      text: `• ${title}`,
    });

    if (source.published_at) {
      richText.push({
        font: { size: 10, italic: true, color: { argb: COLORS.muted } },
        text: `\n   ${formatDate(source.published_at)}`,
      });
    }

    richText.push({
      font: { size: 10, color: { argb: COLORS.accent }, underline: true },
      text: `\n   ${source.url}`,
    });
  });

  return { richText };
}

function projectToRow(project: Project): (string | number | ExcelJS.CellRichTextValue)[] {
  return [
    project.name,
    project.company || "—",
    project.lead_pitch || "—",
    project.city || "—",
    formatCountry(project.country),
    formatDepartment(project.department, project.country),
    project.address || "—",
    formatDate(project.delivery_date),
    project.surface_m2 != null ? Number(project.surface_m2) : "—",
    project.sector || "—",
    formatProjectStatus(project.status),
    formatPeople(project.people),
    formatArticleDates(project.sources),
    project.sources.length > 0 ? buildSourcesRichText(project.sources) : "—",
    "",
  ];
}

export async function exportProjectsToExcel(
  projects: Project[],
  country: string
): Promise<void> {
  const filtered = filterProjectsByCountry(projects, country);
  const countryLabel = getCountryLabel(country);

  const workbook = new ExcelJS.Workbook();
  workbook.creator = "Research Agent";
  workbook.created = new Date();

  const sheet = workbook.addWorksheet("Projects", {
    views: [{ state: "frozen", ySplit: 4, activeCell: "A5" }],
    properties: { defaultRowHeight: 20 },
  });

  const colCount = HEADERS.length;
  const lastCol = String.fromCharCode(64 + colCount);

  sheet.mergeCells(`A1:${lastCol}1`);
  const titleCell = sheet.getCell("A1");
  titleCell.value = "Research Agent — Construction Projects";
  titleCell.font = { bold: true, size: 16, color: { argb: COLORS.titleText } };
  titleCell.fill = { type: "pattern", pattern: "solid", fgColor: { argb: COLORS.titleBg } };
  titleCell.alignment = { horizontal: "center", vertical: "middle" };
  sheet.getRow(1).height = 36;

  sheet.mergeCells(`A2:${lastCol}2`);
  const subtitleCell = sheet.getCell("A2");
  const exportDate = new Date().toLocaleString("en-US", {
    dateStyle: "long",
    timeStyle: "short",
  });
  subtitleCell.value = `${filtered.length} project(s) · ${countryLabel} · Exported on ${exportDate}`;
  subtitleCell.font = { italic: true, size: 10, color: { argb: COLORS.subtitleText } };
  subtitleCell.alignment = { horizontal: "center", vertical: "middle" };
  sheet.getRow(2).height = 22;

  sheet.getRow(3).height = 8;

  const headerRow = sheet.getRow(4);
  headerRow.height = 28;
  HEADERS.forEach((header, index) => {
    const cell = headerRow.getCell(index + 1);
    cell.value = header;
    applyHeaderStyle(cell);
  });

  filtered.forEach((project, index) => {
    const rowNumber = 5 + index;
    const row = sheet.getRow(rowNumber);
    const values = projectToRow(project);
    const isEven = index % 2 === 0;

    values.forEach((value, colIndex) => {
      const cell = row.getCell(colIndex + 1);
      cell.value = value;
      applyDataStyle(cell, isEven);

      if (colIndex === COL.project) {
        cell.font = { bold: true, size: 11 };
      }
      if (colIndex === COL.area && typeof value === "number") {
        cell.numFmt = '#,##0" m²"';
        cell.alignment = { horizontal: "right", vertical: "top" };
      }
      if (colIndex === COL.status && project.status) {
        const statusKey = resolveStatusKey(project.status);
        const statusStyle = statusKey ? COLORS.status[statusKey] : undefined;
        if (statusStyle) {
          cell.fill = {
            type: "pattern",
            pattern: "solid",
            fgColor: { argb: statusStyle.bg },
          };
          cell.font = { bold: true, color: { argb: statusStyle.text }, size: 10 };
          cell.alignment = { horizontal: "center", vertical: "middle" };
        }
      }
      if (colIndex === COL.articleDate) {
        cell.alignment = { horizontal: "center", vertical: "top", wrapText: true };
      }
      if (colIndex === COL.sources && project.sources.length > 0) {
        cell.alignment = { vertical: "top", wrapText: true, indent: 1 };
      }
      if (colIndex === COL.leadPitch && project.lead_pitch) {
        cell.alignment = { vertical: "top", wrapText: true };
        cell.font = { size: 10 };
      }
      if (colIndex === COL.pertinence) {
        cell.dataValidation = {
          type: "list",
          allowBlank: true,
          formulae: ['"Yes,No"'],
        };
        cell.alignment = { horizontal: "center", vertical: "middle" };
      }
    });

    const sourceBlockHeight = project.sources.reduce((height, source) => {
      const lines = 2 + (source.published_at ? 1 : 0);
      return height + lines * 15 + 8;
    }, 0);
    const leadPitchLines = project.lead_pitch
      ? Math.ceil(project.lead_pitch.length / 48)
      : 1;
    row.height = Math.max(28, Math.min(160, sourceBlockHeight, leadPitchLines * 16 + 12));
  });

  HEADERS.forEach((_, index) => {
    sheet.getColumn(index + 1).width = COLUMN_WIDTHS[index];
  });

  sheet.autoFilter = {
    from: { row: 4, column: 1 },
    to: { row: 4 + filtered.length, column: colCount },
  };

  const dateStamp = new Date().toISOString().slice(0, 10);
  const buffer = await workbook.xlsx.writeBuffer();
  const blob = new Blob([buffer], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `projects-research-agent-${country}-${dateStamp}.xlsx`;
  link.click();
  URL.revokeObjectURL(url);
}
