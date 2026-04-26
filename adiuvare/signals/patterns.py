try:
    import re2 as _re
except ImportError:
    import re as _re


sql_pats = [
    (_re.compile(r"""(?i)\b\w+['"]\s*(?:--|\#|/\*)"""), 0.88, "quote_cmnt"),
    (_re.compile(r"(?i)\bselect\b.{0,40}\bfrom\b"), 0.72, "select_from"),
    (_re.compile(r"(?i)\bunion\s+select\b"), 0.92, "union_select"),
    (_re.compile(r"(?i)\bdrop\s+table\b"), 0.95, "drop_table"),
    (_re.compile(r"(?i)\bpg_sleep\s*\("), 0.88, "time_pgsleep"),
    (_re.compile(r"(?i)\bsleep\s*\(\s*\d"), 0.88, "time_sleep"),
    (_re.compile(r"(?i)\bbenchmark\s*\("), 0.86, "time_benchmark"),
    (_re.compile(r"(?i)\bwaitfor\s+delay\b"), 0.88, "time_waitfor"),
    (_re.compile(r"(?i)\bexists\s*\(\s*select\b"), 0.82, "exists_select"),
    (_re.compile(r"(?i)\bextractvalue\s*\("), 0.84, "func_extractvalue"),
    (_re.compile(r"(?i)\bupdatexml\s*\("), 0.84, "func_updatexml"),
    (_re.compile(r"(?i)\bjson_extract\s*\("), 0.72, "func_json_extract"),
    (_re.compile(r"(?i)\binformation_schema\b"), 0.76, "schema_peek"),
]

xss_pats = [
    (_re.compile(r"(?i)<\s*script\b"), 0.72, "script_tag"),
    (_re.compile(r"(?i)javascript\s*:"), 0.68, "js_uri"),
    (_re.compile(r"(?i)on[a-z]{2,20}\s*="), 0.64, "event_attr"),
    (_re.compile(r"(?i)data\s*:\s*text/html"), 0.62, "data_uri"),
]

path_pats = [
    (_re.compile(r"\.\.[/\\]"), 0.61, "path_up"),
    (_re.compile(r"(?i)%2e%2e%2f"), 0.60, "path_up_enc"),
    (_re.compile(r"\x00"), 0.58, "path_null"),
]


def _scan(pats, text: str) -> tuple[bool, float, str]:
    for pat, conf, label in pats:
        if pat.search(text):
            return True, conf, label
    return False, 0.0, ""


def _bool_taut_hit(text: str) -> bool:
    low = " ".join(text.lower().split())
    if " or " not in low or "=" not in low:
        return False
    if "' or " in low and "'='" in low:
        return True
    if '" or ' in low and '"="' in low:
        return True
    return False


def check_sql(text: str) -> tuple[bool, float, str]:
    if _bool_taut_hit(text):
        return True, 0.92, "bool_taut"
    return _scan(sql_pats, text)


def check_xss(text: str) -> tuple[bool, float, str]:
    return _scan(xss_pats, text)


def check_path(text: str) -> tuple[bool, float, str]:
    return _scan(path_pats, text)
