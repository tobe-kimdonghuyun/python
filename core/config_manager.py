import os
import sys
import json
import xml.etree.ElementTree as ET

def find_geninfo_file(filename: str = "$Geninfo$.geninfo") -> str | None:
    """
    설정 파일을 여러 위치에서 탐색합니다.
    순서: 1. 현재 작업 디렉토리(CWD), 2. 실행파일 또는 스크립트 위치
    """
    # 1. CWD
    if os.path.isfile(filename):
        return os.path.abspath(filename)
    
    # 2. EXE/Script Dir
    exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    candidate = os.path.join(exe_dir, filename)
    if os.path.isfile(candidate):
        return os.path.abspath(candidate)
        
    return None

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

def get_base_dir_from_P(config: dict, config_path: str) -> str:
    """
    '-P' (xprj 파일) 경로를 기반으로 기준 디렉토리를 결정합니다.
    xprj 파일이 있는 폴더를 기준으로 삼습니다.
    
    Args:
        config (dict): 설정 데이터
        config_path (str): 설정 파일 경로
        
    Returns:
        str: 결정된 기준 디렉토리 절대 경로
    """
    p_val = get_required_config_value(config, "-P")
    p_val = resolve_config_path_value(config_path, p_val)

    return os.path.dirname(p_val)

def load_config_from_geninfo(geninfo_path: str) -> tuple[dict, str]:
    """
    $Geninfo$.geninfo 파일을 파싱하여 config 딕셔너리를 생성합니다.
    """
    if not os.path.isfile(geninfo_path):
        print(f"파일을 찾을 수 없습니다: {geninfo_path}")
        sys.exit(2)

    try:
        tree = ET.parse(geninfo_path)
        root = tree.getroot()
        
        # 1. Info 태그에서 project, generated 추출
        info_node = root.find(".//Info")
        if info_node is None:
            print(f"XML에서 <Info> 태그를 찾을 수 없습니다: {geninfo_path}")
            sys.exit(2)
            
        project_dir = info_node.get("project")
        generated_dir = info_node.get("generated")
        
        # 2. .json으로 끝나는 첫 번째 <File> url 추출
        file_nodes = root.findall(".//File")
        base_json_url = None
        for fn in file_nodes:
            url = fn.get("url") or fn.get("URL")
            if url and url.lower().endswith(".json"):
                base_json_url = url
                break
        
        if not base_json_url:
            print(f"XML에서 .json 파일을 사용하는 <File> 태그를 찾을 수 없습니다: {geninfo_path}")
            sys.exit(2)
            
        # 3. 경로 조합 (Nexacro N 기준)
        target_token = "Nexacro N"
        idx = base_json_url.find(target_token)
        if idx == -1:
            print(f"URL에서 '{target_token}' 패턴을 찾을 수 없습니다: {base_json_url}")
            sys.exit(2)
            
        nexacro_n_base = base_json_url[:idx + len(target_token)]
        deploy_exe = os.path.join(nexacro_n_base, "Tools", "nexacrodeploy.exe")
        
        # 4. project 폴더에서 .xprj 찾기
        xprj_path = None
        if os.path.isdir(project_dir):
            for f in os.listdir(project_dir):
                if f.lower().endswith(".xprj"):
                    xprj_path = os.path.join(project_dir, f)
                    break
        
        if not xprj_path:
            print(f"프로젝트 폴더({project_dir})에서 .xprj 파일을 찾을 수 없습니다.")
            sys.exit(2)
            
        # 5. nexacrolib 및 generate 경로 설정
        lib_idx = base_json_url.lower().find("nexacrolib")
        if lib_idx != -1:
            b_val = base_json_url[:lib_idx + len("nexacrolib")]
            rule_val = os.path.join(os.path.dirname(b_val), "generate")
        else:
            b_val = ""
            rule_val = ""

        config = {
            "nexacroDeployExecute": deploy_exe,
            "-P": xprj_path,
            "-O": generated_dir,
            "-B": b_val,
            "-GENERATERULE": rule_val
        }
        
        return config, geninfo_path

    except Exception as e:
        print(f"XML 분석 중 오류 발생: {e}")
        sys.exit(2)
