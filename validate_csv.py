
import pandas as pd
from pathlib import Path
from urllib.parse import urlparse

CSV_PATH = Path("output/schemes_candidates.csv")
REPORT_PATH = Path("output/validation_report.csv")

if not CSV_PATH.exists():
    raise FileNotFoundError(f"CSV not found: {CSV_PATH.resolve()}")

df = pd.read_csv(CSV_PATH, dtype=str, keep_default_na=False)
df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

print("\n========== CSV VALIDATION ==========")
print(f"Total rows: {len(df)}")
print(f"Total columns: {len(df.columns)}")
print("\nColumns:", list(df.columns))

# Find relevant columns even if their names differ.
def find_column(keywords):
    for col in df.columns:
        if any(word in col for word in keywords):
            return col
    return None

title_col = find_column(["title", "scheme_name", "name"])
url_col = find_column(["source_url", "source", "url", "link"])
text_col = find_column(["text", "description", "content", "extracted_text"])

issues = []

for index, row in df.iterrows():
    row_number = index + 2  # CSV header is row 1

    if title_col:
        title = row[title_col].strip()
        if not title:
            issues.append((row_number, "Missing title"))
        elif len(title) < 5:
            issues.append((row_number, "Suspiciously short title"))

    if url_col:
        url = row[url_col].strip()
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            issues.append((row_number, "Missing or invalid source URL"))

    if text_col:
        content = row[text_col].strip()
        if len(content) < 100:
            issues.append((row_number, "Very little extracted text"))

# Exact duplicate rows
print("\nExact duplicate rows:", int(df.duplicated().sum()))

# Duplicate URLs
if url_col:
    urls = df[url_col].str.strip()
    print("Repeated source URLs:", int(urls[urls.ne("")].duplicated().sum()))

# Duplicate titles
if title_col:
    titles = df[title_col].str.strip().str.lower()
    print("Repeated titles:", int(titles[titles.ne("")].duplicated().sum()))

# Empty values by column
print("\nEmpty values by column:")
print(df.replace(r"^\s*$", pd.NA, regex=True).isna().sum().to_string())

# Write row-level validation issues
report = pd.DataFrame(issues, columns=["csv_row", "issue"])
report.to_csv(REPORT_PATH, index=False, encoding="utf-8-sig")

print(f"\nRows with validation issues: {len(set(r[0] for r in issues))}")
print(f"Validation report saved to: {REPORT_PATH.resolve()}")
print("\nNote: Structural checks do not verify scheme authenticity.")
