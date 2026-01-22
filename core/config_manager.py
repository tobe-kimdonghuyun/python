import os
import sys
import json

def load_config(config_path: str) -> dict:
    """
    JSON 설정 파일을 읽어 딕셔너리로 반환합니다.
    
    Args:
        config_path (str): 읽을 설정 파일(.json)의 경로
        
    Returns:
        dict: 파싱된 설정 데이터
    """
    if not os.path.isfile(config_path):
        print("config.json 파일을 찾을 수 없습니다:", config_path)
        sys.exit(2)

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        print("config.json 파싱에 실패했습니다:", exc)
        sys.exit(2)

def resolve_config_path_value(config_path: str, value: str) -> str:
    """
    설정 파일 내의 경로 값이 상대 경로일 경우, 설정 파일 위치를 기준으로 절대 경로로 변환합니다.
    
    Args:
        config_path (str): 설정 파일의 경로 (기준점)
        value (str): 변환할 경로 값
        
    Returns:
        str: 변환된 절대 경로 또는 원래 값
    """
    # 값이 문자열이 아니거나 비어있으면 그대로 반환
    if not isinstance(value, str) or not value.strip():
        return value
    # 이미 절대 경로라면 정규화(normpath)만 해서 반환
    if os.path.isabs(value):
        return os.path.normpath(value)
    # 상대 경로라면 설정 파일 디렉토리와 합쳐서 절대 경로 생성
    return os.path.normpath(os.path.join(os.path.dirname(config_path), value))

def get_required_config_value(config: dict, key: str) -> str:
    """
    설정 딕셔너리에서 필수 키 값을 가져옵니다. 값이 없으면 프로그램을 종료합니다.
    
    Args:
        config (dict): 설정 데이터
        key (str): 가져올 키 이름
        
    Returns:
        str: 해당 키의 값
    """
    v = config.get(key)
    if not isinstance(v, str) or not v.strip():
        print(f'config.json에 "{key}" 값이 없거나 올바르지 않습니다.')
        sys.exit(2)
    return v

def load_base_dir_from_F(config: dict, config_path: str) -> str:
    """
    '-F' 옵션 값을 기반으로 기준 디렉토리를 결정합니다.
    '-F'가 파일 경로면 그 파일의 상위 폴더를, 폴더 경로면 그대로 사용합니다.
    
    Args:
        config (dict): 설정 데이터
        config_path (str): 설정 파일 경로
        
    Returns:
        str: 결정된 기준 디렉토리 절대 경로
    """
    # -F 값을 가져오고 절대 경로로 변환
    f_val = get_required_config_value(config, "-F")
    f_val = resolve_config_path_value(config_path, f_val)

    # 파일이면 디렉토리 부분만 추출
    if os.path.isfile(f_val):
        return os.path.dirname(f_val)
    return f_val
