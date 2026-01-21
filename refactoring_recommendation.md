# 구조 개선 제안서 (Refactoring Proposal)

현재 `search.py`는 약 300라인 정도로 아직 관리가 가능한 수준이지만, **설정(Config)**, **탐색(Search)**, **배포(Deploy)** 로직이 한 파일에 섞여 있어 향후 기능이 추가되거나 유지보수할 때 복잡도가 증가할 수 있습니다. 다음과 같은 모듈형 구조로 분리하는 것을 추천합니다.

## 추천 폴더/파일 구조

```text
Project Root/
├── config.json             # 설정 파일
├── main.py                 # 프로그램 진입점 (Entry Point)
└── core/                   # 핵심 로직 모듈 패키지
    ├── __init__.py
    ├── config_manager.py   # 설정 파일 로드 및 경로 처리
    ├── xml_parser.py       # XML 파싱 및 경로 추출
    ├── deploy_manager.py   # 배포 명령 실행 및 파일 이동
    └── file_utils.py       # 파일 검색 및 유틸리티
```

## 모듈별 역할 정의

### 1. `main.py` (진입점)
- `argparse`를 통한 인자 파싱 처리.
- 각 모듈(`config_manager`, `xml_parser`, `deploy_manager`)을 호출하여 전체 흐름(Workflow) 제어.
- 최상위 예외 처리.

### 2. `core/config_manager.py`
- **담당 함수**: `load_config`, `resolve_config_path_value`, `get_required_config_value`
- **역할**: JSON 설정 파일을 읽고, 필요한 경로 값들이 유효한지 검증하고 절대 경로로 변환하는 역할.

### 3. `core/xml_parser.py`
- **담당 함수**: `search_rel_paths_in_services_block`
- **역할**: `typedefinition.xml` 파일을 읽어 특정 패턴(상대 경로)을 찾아내는 순수 로직.

### 4. `core/deploy_manager.py`
- **담당 함수**: `run_nexacro_deploy_repeat`, `build_deploy_base_command`
- **역할**: 외부 프로세스(`nexacroDeployExecute`) 실행 및 로깅 담당.

### 5. `core/file_utils.py`
- **담당 함수**: `collect_files_for_FILE_from_F`, `move_js_files_from_file_dir`
- **역할**: 파일 시스템 탐색, `.js` 파일 이동 등 파일 조작 관련 유틸리티.

## 분리 시 장점 (Benefits)

1. **유지보수성 (Maintainability)**: 배포 로직을 고칠 때 XML 파싱 코드를 건드릴 위험이 줄어듭니다.
2. **가독성 (Readability)**: 파일 하나당 코드가 짧아져서(50~100줄) 읽기 편해집니다.
3. **재사용성 (Reusability)**: 나중에 `config` 로딩 로직이나 `xml` 파싱 로직을 다른 스크립트에서도 `import`해서 쓸 수 있습니다.
4. **테스트 용이성 (Testability)**: UI나 실행 없이 XML 파싱만 따로 테스트하거나, 설정 로드만 따로 검증하기 쉬워집니다.

---


---

## 실행 명령어 변경 사항 (Execution Command)

리팩토링 후에도 **실행 명령어는 기존과 완전히 동일하게 유지**할 수 있습니다.

1. **진입점 파일명 유지**: `main.py` 대신 기존처럼 `search.py`라는 이름으로 진입점 파일을 만들면 됩니다.
2. **명령어 호환**:
   ```bash
   # 기존 명령어 그대로 사용 가능
   python search.py config.json [옵션]
   ```
   사용자는 내부 구조가 바뀌었는지 신경 쓸 필요 없이, 기존 스크립트나 배치 파일 등을 수정하지 않고 그대로 사용할 수 있습니다.
