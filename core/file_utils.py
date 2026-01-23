import os
import sys
import shutil
from .config_manager import resolve_config_path_value, get_required_config_value, load_base_dir_from_F

def compute_effective_O_values(config: dict, config_path: str, rel_paths: list[str]) -> dict[str, str]:
    """
    설정 파일의 -O 옵션 값과 Services에서 추출한 상대 경로들을 결합하여,
    실제로 배포 결과물이 저장될 절대 경로를 상대 경로 기준으로 매핑합니다.
    
    Args:
        config (dict): 설정 데이터
        config_path (str): 설정 파일 경로
        rel_paths (list[str]): xml_parser에서 추출한 상대 경로 리스트
        
    Returns:
        dict[str, str]: 상대 경로 -> 결합된 절대 경로(-O) 매핑
    """
    # 기본 -O 값 가져오기 (절대 경로 변환)
    base_o = resolve_config_path_value(config_path, get_required_config_value(config, "-O"))
    o_values: dict[str, str] = {}

    for rp in rel_paths:
        norm_rp = os.path.normpath(rp)
        # base_o 경로와 상대 경로(rp)를 결합
        eff = os.path.normpath(os.path.join(base_o, rp))
        if norm_rp not in o_values:
            o_values[norm_rp] = eff

    return o_values

def collect_files_for_FILE_from_F(config: dict, config_path: str, rel_paths: list[str]) -> dict[str, list[str]]:
    """
    -F 기준 경로와 Services의 상대 경로를 결합하여 실제 파일(.xfdl, .xjs) 목록을 수집합니다.
    
    Args:
        config (dict): 설정 데이터
        config_path (str): 설정 파일 경로
        rel_paths (list[str]): xml_parser에서 추출한 상대 경로 리스트
        
    Returns:
        dict[str, list[str]]: 상대 경로 기준 배포 대상 파일 절대 경로 리스트
    """
    # -F 옵션으로 기준 디렉토리 로드
    base_f_dir = load_base_dir_from_F(config, config_path)

    allowed_extensions = {".xfdl", ".xjs"}

    def is_allowed_file(path: str) -> bool:
        return os.path.splitext(path)[1].lower() in allowed_extensions

    out_files: dict[str, list[str]] = {}
    seen_targets = set()  # 중복 경로 체크용

    for rp in rel_paths:
        norm_rp = os.path.normpath(rp)
        # 기준 디렉토리와 상대 경로 결합하여 탐색 대상 경로 생성
        target = os.path.normpath(os.path.join(base_f_dir, rp))

        if target in seen_targets:
            continue
        seen_targets.add(target)

        if not os.path.exists(target):
            print("경로가 존재하지 않습니다:", target)
            continue

        collected: set[str] = set()

        # 대상이 파일인 경우 바로 추가
        if os.path.isfile(target):
            if is_allowed_file(target):
                collected.add(target)
        else:
            # 대상이 디렉토리인 경우 내부 순회하며 파일 수집
            for name in os.listdir(target):
                full = os.path.join(target, name)
                if os.path.isfile(full) and is_allowed_file(full):
                    collected.add(full)

        if collected:
            out_files.setdefault(norm_rp, [])
            out_files[norm_rp].extend(sorted(collected))

    # 중복 제거 및 정렬하여 반환
    return {rp: sorted(set(files)) for rp, files in out_files.items()}

def move_js_files_from_file_dir(file_path: str, o_dir: str) -> None:
    """
    배포 실행 후 생성된 .js 파일들을 원본 폴더에서 대상 폴더(-O 경로)로 이동시킵니다.
    
    Args:
        file_path (str): 원본 파일 경로 (-FILE 인자로 사용된 값)
        o_dir (str): 이동할 대상 디렉토리 경로 (-O 값)
    """
    src_dir = os.path.dirname(file_path) # 원본 파일이 있는 디렉토리
    if not os.path.isdir(src_dir):
        print("원본 폴더가 존재하지 않습니다:", src_dir)
        return

    # 대상 디렉토리가 없으면 생성
    os.makedirs(o_dir, exist_ok=True)

    for name in os.listdir(src_dir):
        # .js 확장자만 처리
        if os.path.splitext(name)[1].lower() != ".js":
            continue

        src_path = os.path.join(src_dir, name)
        if not os.path.isfile(src_path):
            continue

        dest_path = os.path.join(o_dir, name)
        
        # 원본과 대상이 같은 경우 이동 불필요
        if os.path.abspath(src_path) == os.path.abspath(dest_path):
            continue
            
        # 이동할 위치에 상위 폴더가 없으면 생성
        dest_dir = os.path.dirname(dest_path)
        if dest_dir:
            os.makedirs(dest_dir, exist_ok=True)
            
        # 이미 대상 파일이 존재하면 삭제 (덮어쓰기 준비)
        if os.path.exists(dest_path):
            os.remove(dest_path)

        # 파일 이동
        shutil.move(src_path, dest_path)
