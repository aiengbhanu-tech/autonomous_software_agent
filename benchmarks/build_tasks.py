"""Deterministic, manually specified contracts. No external datasets or models.

The oracle-bearing manifest is evaluator data, never included in model prompts.
Run from repository root: python benchmarks/build_tasks.py
"""
import json
from pathlib import Path

tasks = []


def add(category, name, signature, issue, broken, fixed, cases):
    number = 1 + sum(t["category"] == category for t in tasks)
    tasks.append({"id": f"{category}-{number:03d}", "category": category,
                  "function": name, "issue": issue,
                  "initial_source": f"def {name}({signature}):\n    return {broken}\n",
                  "reference_source": f"def {name}({signature}):\n    return {fixed}\n",
                  "public_cases": [{"args": a, "expected": b} for a, b in cases[:3]],
                  "hidden_cases": [{"args": a, "expected": b} for a, b in cases[3:]]})


add("auth", "authentication_status", "password", "The authentication endpoint sometimes returns 500 when passwords exceed the supported length. Diagnose and fix it. Contract: strings of at most 72 UTF-8 bytes return 200; longer strings return 422. Never truncate. Preserve the exact boundary.",
    "200 if len(password.encode('utf-8')) <= 72 else 500", "200 if len(password.encode('utf-8')) <= 72 else 422",
    [(["abc"], 200), (["x" * 73], 422), (["🔐" * 19], 422), (["x" * 72], 200), (["é" * 36], 200), (["é" * 37], 422)])
add("auth", "clean_token", "token", "Token parsing preserves accidental edge whitespace. Strip whitespace from both ends without changing interior spaces.", "token", "token.strip()",
    [([" abc "], "abc"), (["\tabc\n"], "abc"), (["a b"], "a b"), (["   "], ""), (["x"], "x")])
add("auth", "is_bearer", "header", "Bearer prefix check accepts bare tokens. Require the exact case-sensitive prefix 'Bearer ' including its space.", "header.startswith('Bearer')", "header.startswith('Bearer ')",
    [(["Bearer abc"], True), (["Bearerabc"], False), (["Basic x"], False), (["Bearer"], False), (["bearer x"], False)])
add("auth", "can_admin", "role", "Admin authorization incorrectly permits editors. Return True only for exact role 'admin'.", "role in ['admin', 'editor']", "role == 'admin'",
    [(["admin"], True), (["editor"], False), (["viewer"], False), (["ADMIN"], False), ([""], False)])
add("auth", "password_valid", "password", "Password minimum length rejects valid eight-character passwords. Require at least eight characters.", "len(password) > 8", "len(password) >= 8",
    [(["12345678"], True), (["short"], False), (["123456789"], True), ([""], False), (["é" * 8], True)])

add("pagination", "offset", "page, size", "Page numbers start at 1. Compute the zero-based row offset.", "page * size", "(page - 1) * size",
    [([1, 10], 0), ([2, 10], 10), ([3, 5], 10), ([1, 1], 0), ([6, 7], 35)])
add("pagination", "page_count", "total, size", "Page counts round down and lose the partial last page. Return ceiling(total / size); size is positive.", "total // size", "(total + size - 1) // size",
    [([11, 10], 2), ([20, 10], 2), ([0, 10], 0), ([1, 100], 1), ([25, 6], 5)])
add("pagination", "page_items", "items, start, size", "Page slicing treats size as an absolute endpoint. Return up to size elements starting at start.", "items[start:size]", "items[start:start + size]",
    [([[1,2,3,4], 1, 2], [2,3]), ([[1,2], 0, 1], [1]), ([[1,2,3], 2, 4], [3]), ([[],0,2], []), ([[0,1,2,3,4],3,1], [3])])
add("pagination", "has_next", "page, size, total", "The last full page claims another page exists. Return whether page * size is strictly less than total.", "page * size <= total", "page * size < total",
    [([1,10,10], False), ([1,10,11], True), ([2,10,15], False), ([1,1,0], False), ([2,3,7], True)])
add("pagination", "normalize_page", "page", "Negative and zero page numbers must normalize to 1; positive pages remain unchanged.", "min(1, page)", "max(1, page)",
    [([0],1), ([3],3), ([-4],1), ([1],1), ([20],20)])

add("numeric", "percentage", "part, total", "Percentage returns a ratio instead of percent. Zero total returns 0.0.", "part / total if total else 0.0", "part / total * 100 if total else 0.0",
    [([1,4],25.0), ([0,0],0.0), ([3,3],100.0), ([1,8],12.5), ([0,8],0.0)])
add("numeric", "discount_price", "price, percent", "Discount is subtracted as a fixed amount. Apply the given percentage discount.", "price - percent", "price * (1 - percent / 100)",
    [([200,10],180.0), ([100,0],100.0), ([80,25],60.0), ([50,100],0.0), ([40,50],20.0)])
add("numeric", "average", "values", "Average divides by one too many. Return arithmetic mean, or 0.0 for empty input.", "sum(values) / (len(values) + 1)", "sum(values) / len(values) if values else 0.0",
    [([[2,4]],3.0), ([[]],0.0), ([[5]],5.0), ([[-2,2]],0.0), ([[3,6,9]],6.0)])
add("numeric", "clamp", "value, low, high", "Clamp always returns low. Constrain value to inclusive bounds, where low <= high.", "min(low, max(high, value))", "max(low, min(high, value))",
    [([5,0,10],5), ([-3,0,10],0), ([20,0,10],10), ([0,0,0],0), ([-5,-10,-2],-5)])
add("numeric", "ceil_div", "value, divisor", "Integer division loses remainders. Return ceiling division for nonnegative values and positive divisors.", "value // divisor", "(value + divisor - 1) // divisor",
    [([5,2],3), ([6,3],2), ([0,7],0), ([1,8],1), ([19,4],5)])

add("text", "slug", "text", "Slug generation misses case and surrounding whitespace. Strip, lowercase, then replace each space with a hyphen.", "text.replace(' ', '-')", "text.strip().lower().replace(' ', '-')",
    [([" Hello World "],"hello-world"), (["ABC"],"abc"), (["a b"],"a-b"), ([""],""), ([" X  Y "],"x--y")])
add("text", "file_extension", "filename", "File extension should be lowercase text after the last dot, or empty when no dot exists.", "filename.split('.')[-1]", "filename.split('.')[-1].lower() if '.' in filename else ''",
    [(["a.PDF"],"pdf"), (["README"],""), (["a.tar.gz"],"gz"), (["x."],""), (["PHOTO.JPG"],"jpg")])
add("text", "remove_prefix", "text, prefix", "Prefix removal deletes matching interior text. Remove prefix exactly once only when text starts with it.", "text.replace(prefix, '')", "text[len(prefix):] if text.startswith(prefix) else text",
    [(["prevaluepre","pre"],"valuepre"), (["valuepre","pre"],"valuepre"), (["prex","pre"],"x"), (["x",""],"x"), (["abc","z"],"abc")])
add("text", "preview", "text, limit", "Preview returns one character too many. Return the first limit characters; nonnegative limit.", "text[:limit + 1]", "text[:limit]",
    [(["abcdef",3],"abc"), (["a",5],"a"), (["abc",0],""), (["",0],""), (["éabc",1],"é")])
add("text", "normalize_email", "email", "Email normalization leaves whitespace. Strip edges and lowercase the full address.", "email.lower()", "email.strip().lower()",
    [([" A@B.COM "],"a@b.com"), (["X@Y.io"],"x@y.io"), (["\ta@b.c\n"],"a@b.c"), ([""],""), ([" q+X@B.C "],"q+x@b.c")])

add("collections", "last_or_none", "items", "Last item helper returns the first item. Return the last item or None for empty input.", "items[0] if items else None", "items[-1] if items else None",
    [([[1,2,3]],3), ([[]],None), ([[7]],7), ([[None,False]],False), ([["a","b"]],"b")])
add("collections", "sorted_unique", "items", "Sorted output retains duplicates. Return sorted distinct integers.", "sorted(items)", "sorted(set(items))",
    [([[3,1,3]],[1,3]), ([[]],[]), ([[2,2]],[2]), ([[-1,0,-1]],[-1,0]), ([[5,3,4]],[3,4,5])])
add("collections", "contains", "items, value", "Membership is inverted. Return True when value exists in items.", "value not in items", "value in items",
    [([[1,2],2],True), ([[1],3],False), ([[],0],False), ([[None],None],True), ([["x"],"x"],True)])
add("collections", "get_default", "mapping, key, default", "Fallback overwrites valid falsey values. Use default only for missing keys.", "mapping.get(key) or default", "mapping.get(key, default)",
    [([{"x":0},"x",9],0), ([{},"x",9],9), ([{"x":False},"x",True],False), ([{"x":None},"x",9],None), ([{"x":""},"x","d"],"")])
add("collections", "rotate_left", "items, amount", "Rotation uses raw offset and fails above list length. Rotate left modulo length; empty list stays empty.", "items[amount:] + items[:amount]", "items[amount % len(items):] + items[:amount % len(items)] if items else []",
    [([[1,2,3],4],[2,3,1]), ([[],5],[]), ([[1,2,3],1],[2,3,1]), ([[1,2],0],[1,2]), ([[1,2,3],-1],[3,1,2])])

add("validation", "age_allowed", "age", "Eligible ages include both 18 and 65. Return whether age is in that inclusive range.", "18 < age < 65", "18 <= age <= 65",
    [([18],True), ([65],True), ([17],False), ([40],True), ([66],False)])
add("validation", "valid_port", "port", "Port validation permits 0 and rejects 65535. Valid integer ports range from 1 through 65535.", "0 <= port < 65535", "1 <= port <= 65535",
    [([0],False), ([65535],True), ([80],True), ([-1],False), ([65536],False)])
add("validation", "ranges_overlap", "a, b, c, d", "Closed intervals [a,b] and [c,d] overlap even at shared endpoints. Bounds are ordered.", "a < d and c < b", "a <= d and c <= b",
    [([1,3,3,5],True), ([1,2,4,5],False), ([1,5,2,3],True), ([2,2,2,2],True), ([-5,-3,-2,0],False)])
add("validation", "leap_year", "year", "Leap year rule ignores centuries. Gregorian years divide by 4, except centuries unless divisible by 400.", "year % 4 == 0", "year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)",
    [([1900],False), ([2000],True), ([2024],True), ([2023],False), ([2100],False)])
add("validation", "is_even", "number", "Even-number helper is reversed, including for zero and negatives.", "number % 2 != 0", "number % 2 == 0",
    [([0],True), ([3],False), ([4],True), ([-2],True), ([-3],False)])

add("finance", "with_tax", "net, rate", "Tax total adds rate as currency. Add net multiplied by the fractional tax rate.", "net + rate", "net * (1 + rate)",
    [([100,0.25],125.0), ([80,0.5],120.0), ([0,0.1],0.0), ([10,0.0],10.0), ([40,0.25],50.0)])
add("finance", "to_cents", "amount", "Cent conversion truncates fractional cents. Round amount * 100 using Python's round, then return int.", "int(amount * 100)", "int(round(amount * 100))",
    [([1.239],124), ([1.231],123), ([0.0],0), ([2.999],300), ([-1.239],-124)])
add("finance", "capped_fee", "amount, rate, cap", "Fee cap acts as a minimum. Return the smaller of amount * rate and cap.", "max(amount * rate, cap)", "min(amount * rate, cap)",
    [([100,0.1,5],5), ([10,0.1,5],1.0), ([0,0.1,5],0.0), ([50,0.1,5],5.0), ([1000,0.02,10],10)])
add("finance", "line_total", "quantity, unit_price", "Invoice line adds quantity to price. Multiply the two values.", "quantity + unit_price", "quantity * unit_price",
    [([3,10],30), ([0,5],0), ([1,7],7), ([2,2.5],5.0), ([4,0],0)])
add("finance", "change_due", "paid, total", "Change sign is reversed. Return paid minus total, including negative balances.", "total - paid", "paid - total",
    [([20,15],5), ([10,10],0), ([5,10],-5), ([0,0],0), ([25,7],18)])

add("units", "celsius_to_f", "celsius", "Celsius conversion omits the Fahrenheit offset. Use C * 9 / 5 + 32.", "celsius * 9 / 5", "celsius * 9 / 5 + 32",
    [([0],32.0), ([100],212.0), ([-40],-40.0), ([10],50.0), ([20],68.0)])
add("units", "km_to_miles", "km", "Kilometer conversion uses the inverse factor. Multiply kilometers by exactly 0.625 for this contract.", "km / 0.625", "km * 0.625",
    [([8],5.0), ([0],0.0), ([16],10.0), ([1],0.625), ([4],2.5)])
add("units", "minutes_to_seconds", "minutes", "Minute conversion divides by 60. Return minutes multiplied by 60.", "minutes // 60", "minutes * 60",
    [([1],60), ([2],120), ([0],0), ([10],600), ([3],180)])
add("units", "rectangle_area", "width, height", "Rectangle area computes perimeter instead. Return width * height.", "2 * (width + height)", "width * height",
    [([3,4],12), ([0,4],0), ([5,5],25), ([1,7],7), ([2,3],6)])
add("units", "speed", "distance, hours", "Speed multiplies distance by time. Divide instead, returning 0.0 when time is zero.", "distance * hours", "distance / hours if hours else 0.0",
    [([100,2],50.0), ([0,2],0.0), ([10,0],0.0), ([9,3],3.0), ([5,1],5.0)])

add("logic", "exclusive_or", "a, b", "Boolean exclusive-or currently behaves as OR. True exactly when Boolean inputs differ.", "a or b", "a != b",
    [([True,True],False), ([True,False],True), ([False,False],False), ([False,True],True), ([True,True],False)])
add("logic", "majority", "a, b, c", "Voting accepts a single yes vote. Require at least two of three Boolean inputs.", "a or b or c", "(a and b) or (a and c) or (b and c)",
    [([True,False,False],False), ([True,True,False],True), ([False,False,False],False), ([False,True,True],True), ([True,True,True],True)])
add("logic", "is_weekend", "day", "Weekdays use Monday=0 through Sunday=6. Only 5 and 6 are weekend; invalid indices return False.", "day >= 5", "day in [5, 6]",
    [([5],True), ([6],True), ([7],False), ([4],False), ([-1],False)])
add("logic", "strictly_between", "value, low, high", "Strict bounds accidentally include endpoints. Require low < value < high.", "low <= value <= high", "low < value < high",
    [([0,0,10],False), ([10,0,10],False), ([5,0,10],True), ([-1,0,10],False), ([1,1,1],False)])
add("logic", "can_write", "active, role", "Inactive admins can write and active viewers can write. Require active AND role in ['admin', 'editor'].", "active or role == 'admin'", "active and role in ['admin', 'editor']",
    [([False,"admin"],False), ([True,"viewer"],False), ([True,"editor"],True), ([True,"admin"],True), ([False,"editor"],False)])

add("strings", "ends_with", "text, suffix", "Suffix helper checks the start. Check whether text ends with suffix.", "text.startswith(suffix)", "text.endswith(suffix)",
    [(["report.pdf",".pdf"],True), (["pdf-report","pdf"],False), (["abc","x"],False), (["abc",""],True), (["xabc","abc"],True)])
add("strings", "split_csv", "text", "Simple comma-separated parser uses semicolons. Split on commas, preserving empty fields; no quoting support.", "text.split(';')", "text.split(',')",
    [(["a,b"],["a","b"]), (["a,,b"],["a","","b"]), ([""],[""]), (["x"],["x"]), (["x,y,z"],["x","y","z"])])
add("strings", "reverse_text", "text", "Reverse helper returns input unchanged. Reverse Unicode code points.", "text", "text[::-1]",
    [(["abc"],"cba"), ([""],""), (["a"],"a"), (["éx"],"xé"), (["1234"],"4321")])
add("strings", "repeat", "text, count", "Repeater adds one unwanted copy. Repeat text count times for nonnegative count.", "text * (count + 1)", "text * count",
    [(["a",2],"aa"), (["x",0],""), (["ab",1],"ab"), (["",3],""), (["é",3],"ééé")])
add("strings", "is_palindrome", "text", "Palindrome check is inverted. Compare text to its reverse, case-sensitive, no normalization.", "text != text[::-1]", "text == text[::-1]",
    [(["aba"],True), (["ab"],False), ([""],True), (["x"],True), (["Aa"],False)])

if __name__ == "__main__":
    assert len(tasks) == 50
    path = Path(__file__).with_name("tasks.json")
    path.write_text(json.dumps({"version": "1.0", "label": "controlled-microbugs-v1", "tasks": tasks}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(tasks)} tasks to {path}")

