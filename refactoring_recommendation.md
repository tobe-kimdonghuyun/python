# 구조 개선 제안서 (Refactoring Proposal)

현재 `search.py`는 약 300라인 정도로 아직 관리가 가능한 수준이지만, **설정(Config)**, **탐색(Search)**, **배포(Deploy)** 로직이 한 파일에 섞여 있어 향후 기능이 추가되거나 유지보수할 때 복잡도가 증가할 수 있습니다. 다음과 같은 모듈형 구조로 분리하는 것을 추천합니다. 그리고 기존 search.py 파일은 유지하고 main.py를 실행하면 기존과 동일하게 작동할 수 있도록 합니다.

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

- **담당 함수**: `find_geninfo_file`, `load_config_from_geninfo`, `load_config`, `resolve_config_path_value`
- **역할**: 설정 파일을 다각도로 탐색(CWD/EXE)하고, XML 또는 JSON 형식의 결합된 배포 정보를 로드하여 시스템 전반에 일관된 설정을 제공.

### 3. `core/xml_parser.py`

- **담당 함수**: `search_rel_paths_in_services_block`
- **역할**: `typedefinition.xml` 파일을 정밀 파싱하여 배포 대상이 될 상대 경로 토큰을 추출하는 비즈니스 로직.

### 4. `core/deploy_manager.py`

- **담당 함수**: `run_project_deploy_cycle`, `run_file_deploy_cycle`, `build_deploy_base_command`
- **역할**: 2.1~2.6의 최적화된 배포 시퀀스를 제어. 프로젝트 전체 구조와 개별 파일을 순차적으로 배포하고 외부 명령을 실행.

### 5. `core/file_utils.py`

- **담당 함수**: `collect_files_for_FILE_from_P`, `move_js_files_from_file_dir`, `cleanup_test_files`
- **역할**: 파일 검색, 이동, 삭제 등 저수준 파일 시스템 조작 및 정리 작업 전담.

## 분리 시 장점 (Benefits)

1. **유지보수성 (Maintainability)**: 배포 엔진의 동작 방식이 바뀌어도 XML 파싱이나 설정 로드 코드를 수정할 필요가 없습니다.
2. **환경 대응성 (Environment Agnostic)**: 다양한 실행 환경(CLI, IDE 외부 도구 등)에서 경로 이슈 없이 설정 파일을 로드할 수 있습니다.
3. **보안성 (Robustness)**: 임시 파일 위치 최적화 등을 통해 `PermissionError`와 같은 시스템 권한 문제를 사전에 방지합니다.
4. **일관성 (Consistency)**: `search.py`(싱글)와 `main.py`(모듈)가 핵심 로직을 공유하므로, 한 곳의 개선 사항이 전체 시스템에 즉시 반영됩니다.

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
