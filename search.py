import argparse
import json
import os
import sys
import re

def parse_args():
    p = argparse.ArgumentParser(
        description="로컬 파일(또는 폴더)에서 문자열을 검색합니다."
    )

    # 필수: 파일 경로, 키워드
    p.add_argument("-F", "--file", required=True,
                   help="검색 대상 폴더 경로 (자동으로 typedefinition.xml 추가)")
    p.add_argument("-K", "--keyword", required=True,
                   help="검색 키워드 또는 -F 하위 경로(폴더가 있으면 파일 개수 JSON 생성)")

    # (확장 대비) 선택 옵션들
    p.add_argument("-i", "--ignore-case", action="store_true", help="대소문자 무시")
    p.add_argument("--contains-only", action="store_true",
                   help="라인 전체 출력 대신 '발견 여부'만 표시")
    p.add_argument("--max-hits", type=int, default=0,
                   help="최대 출력 개수(0이면 제한 없음)")
    p.add_argument("--encoding", default="utf-8",
                   help="파일 인코딩(기본 utf-8)")
    p.add_argument("--errors", default="ignore",
                   choices=["ignore", "replace", "strict"],
                   help="디코딩 에러 처리(기본 ignore)")
    p.add_argument("--no-line-number", action="store_true",
                   help="줄번호 출력하지 않음")

    # 속성 값만 추출 (단일 속성)
    p.add_argument("--extract-attr", default="",
                   help='지정한 XML 속성 값만 추출해서 출력 (예: url, src, path). 비우면 라인 출력')

    # ✅ 추가: 두 속성을 한 줄에서 같이 추출해서 "a,b"로 출력
    # 예: --extract-pair prefixid,url
    p.add_argument("--extract-pair", default="",
                   help='두 속성을 같이 추출해 "attr1,attr2"로 출력 (예: prefixid,url)')

    # 중복 제거 옵션 (추출 모드에서 유용)
    p.add_argument("--unique", action="store_true", help="추출 결과 중복 제거")

    # 앞으로 폴더 검색 같은 요구가 붙을 가능성 대비 (지금은 사용 안 해도 됨)
    p.add_argument("--path", default="",
                   help="(확장용) 폴더/패턴 검색을 붙일 때 사용할 경로")

    return p.parse_args()

def search_in_file(file_path: str, keyword: str, ignore_case: bool,
                   encoding: str, errors: str,
                   show_line_number: bool, contains_only: bool,
                   max_hits: int,
                   extract_attr: str = "",
                   extract_pair: str = "",
                   unique: bool = False) -> int:
    if not os.path.isfile(file_path):
        print("파일이 존재하지 않습니다:", file_path)
        return 2

    hits = 0
    seen = set()

    keyword_cmp = keyword.lower() if ignore_case else keyword

    # 단일 속성 추출 정규식
    attr_pattern = None
    if extract_attr:
        attr_pattern = re.compile(rf'{re.escape(extract_attr)}="([^"]+)"')

    # ✅ 두 속성 추출 준비
    pair_attrs = []
    pair_patterns = None
    if extract_pair:
        # "prefixid,url" 형태
        pair_attrs = [a.strip() for a in extract_pair.split(",") if a.strip()]
        if len(pair_attrs) != 2:
            print('오류: --extract-pair 는 "attr1,attr2" 형태로 2개만 지정해야 합니다. 예) prefixid,url')
            return 2
        pair_patterns = (
            re.compile(rf'{re.escape(pair_attrs[0])}="([^"]+)"'),
            re.compile(rf'{re.escape(pair_attrs[1])}="([^"]+)"')
        )

    with open(file_path, "r", encoding=encoding, errors=errors) as f:
        for line_num, line in enumerate(f, start=1):
            hay = line.lower() if ignore_case else line

            if keyword_cmp in hay:
                hits += 1

                if contains_only:
                    if hits == 1:
                        print("문구 발견!")
                    if max_hits > 0 and hits >= max_hits:
                        break
                    continue

                # ✅ 1) 두 속성 같이 추출 모드 (우선순위 높게)
                if pair_patterns:
                    m1 = pair_patterns[0].search(line)
                    m2 = pair_patterns[1].search(line)
                    if m1 and m2:
                        v1 = m1.group(1)
                        v2 = m2.group(1)

                        out = f"{v1},{v2}"  # CSV 한 줄처럼 사용 가능

                        if unique:
                            if out in seen:
                                if max_hits > 0 and hits >= max_hits:
                                    break
                                continue
                            seen.add(out)

                        print(out)

                # 2) 단일 속성 추출 모드
                elif attr_pattern:
                    m = attr_pattern.search(line)
                    if m:
                        value = m.group(1)

                        if unique:
                            if value in seen:
                                if max_hits > 0 and hits >= max_hits:
                                    break
                                continue
                            seen.add(value)

                        print(value)

                # 3) 기존 동작: 라인 출력
                else:
                    if show_line_number:
                        print(f"{line_num}번째 줄: {line.strip()}")
                    else:
                        print(line.strip())

                if max_hits > 0 and hits >= max_hits:
                    break

    return 0 if hits > 0 else 1  # 0=발견, 1=미발견

def count_files_in_directory(target_dir: str) -> int:
    count = 0
    with os.scandir(target_dir) as entries:
        for entry in entries:
            if entry.is_file():
                count += 1
    return count

def write_file_count_json(target_dir: str) -> str:
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "file_count.json")
    data = {
        "path": os.path.abspath(target_dir),
        "file_count": count_files_in_directory(target_dir),
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return output_path

def main():
    args = parse_args()

    base_dir = args.file
    if os.path.isfile(base_dir) or os.path.splitext(base_dir)[1].lower() == ".xml":
        base_dir = os.path.dirname(base_dir)
    combined_path = os.path.join(base_dir, args.keyword)
    if os.path.isdir(combined_path):
        output_path = write_file_count_json(combined_path)
        print("JSON 파일 생성:", output_path)
        sys.exit(0)

    file_path = os.path.join(base_dir, "typedefinition.xml")

    exit_code = search_in_file(
        file_path=file_path,
        keyword=args.keyword,
        ignore_case=args.ignore_case,
        encoding=args.encoding,
        errors=args.errors,
        show_line_number=not args.no_line_number,
        contains_only=args.contains_only,
        max_hits=args.max_hits,
        extract_attr=args.extract_attr,
        extract_pair=args.extract_pair,
        unique=args.unique
    )
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
