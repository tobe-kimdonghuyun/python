import os
import re

def search_rel_paths_in_services_block(
    file_path: str,
    encoding: str,
    errors: str,
    contains_only: bool,
    max_hits: int,
) -> tuple[int, list[str]]:
    """
    typedefinition.xml 파일의 <Services>...</Services> 블록 내에서 
    '../'로 시작하는 상대 경로 패턴을 검색합니다.

    Args:
        file_path (str): 검색할 XML 파일 경로
        encoding (str): 파일 인코딩 (기본 utf-8)
        errors (str): 디코딩 에러 처리 방식 ('ignore', 'replace', 'strict')
        contains_only (bool): True일 경우 발견 여부만 확인하고 경로는 수집하지 않음
        max_hits (int): 최대 검색 개수 (0이면 제한 없음)

    Returns:
        tuple[int, list[str]]: (종료 코드(0:성공/발견, 1:실패/미발견), 감지된 상대 경로 리스트)
    """
    if not os.path.isfile(file_path):
        print("파일이 존재하지 않습니다:", file_path)
        return 2, []

    hits = 0
    rel_paths: list[str] = []

    # 정규식 패턴 컴파일
    # \.\./[^\"'\s<>]+ : ../ 로 시작하고 따옴표, 공백, 괄호가 나오기 전까지의 문자열 매칭
    rel_path_pattern = re.compile(r"\.\./[^\"'\s<>]+")
    open_services = re.compile(r"<\s*Services\b", re.IGNORECASE)  # <Services ... 시작 태그
    close_services = re.compile(r"</\s*Services\s*>", re.IGNORECASE) # </Services> 종료 태그

    in_services = False  # 현재 <Services> 블록 내부에 있는지 여부 플래그

    with open(file_path, "r", encoding=encoding, errors=errors) as f:
        for line in f:
            # <Services> 시작 태그 발견 시 플래그 활성화
            if not in_services and open_services.search(line):
                in_services = True

            if in_services:
                # 라인 내에서 상대 경로 패턴 검색
                matches = rel_path_pattern.findall(line)
                if matches:
                    for m in matches:
                        hits += 1

                        # --contains-only 옵션: 발견 즉시 로깅하고 종료할 수 있음
                        if contains_only:
                            if hits == 1:
                                print("문구 발견!")
                            if max_hits > 0 and hits >= max_hits:
                                break
                            continue

                        # 경로 수집
                        rel_paths.append(m)

                        # 최대 히트 수 도달 시 중단
                        if max_hits > 0 and hits >= max_hits:
                            break

                    if max_hits > 0 and hits >= max_hits:
                        break

            # </Services> 종료 태그 발견 시 플래그 비활성화
            if in_services and close_services.search(line):
                in_services = False

    # 하나라도 발견되면 exit_code 0, 아니면 1
    return (0 if hits > 0 else 1), rel_paths
