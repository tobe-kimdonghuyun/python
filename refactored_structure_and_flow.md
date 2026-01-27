# 리팩토링된 소스 (Refactored Source) 구조 및 흐름 분석

이 문서는 모듈화된(`main.py` + `core/`) 리팩토링 코드의 내부 구조와 실행 흐름을 분석하여 기술합니다.

## 1. 파일 구조 (File Structure)

리팩토링된 구조는 진입점(`main.py`)과 기능별 모듈(`core/`)로 분리되어 있습니다.

```text
Project Root/
├── main.py                 # 프로그램 진입점 (Entry Point)
└── core/                   # 핵심 기능 모듈 패키지
    ├── __init__.py
    ├── config_manager.py   # 설정 파일 탐색/로드 및 경로 처리 (find_geninfo_file 포함)
    ├── xml_parser.py       # XML 파싱 및 상대 경로 추출
    ├── file_utils.py       # 파일 시스템 탐색 및 소스 파일 수집
    └── deploy_manager.py   # 배포 시퀀스(Phase 1, 2) 제어 및 명령 실행
```

### 모듈별 핵심 함수

| 모듈                      | 함수명                                 | 역할                                               |
| :------------------------ | :------------------------------------- | :------------------------------------------------- |
| **`main.py`**             | `main()`                               | 전체 시퀀스(2.1~2.6) 조율 및 임시 XML 관리         |
| **`core/config_manager`** | `find_geninfo_file()`                  | CWD 및 EXE 폴더에서 설정 파일을 지능적으로 검색    |
|                           | `load_config_from_geninfo()`           | `.geninfo` 파일의 XML 정보를 배포 설정 Dict로 변환 |
| **`core/xml_parser`**     | `search_rel_paths_in_services_block()` | XML 파일 파싱 및 상대 경로 패턴 추출               |
| **`core/deploy_manager`** | `run_project_deploy_cycle()`           | Phase 1: 전체 프로젝트 구조 배포 (-O / -D)         |
|                           | `run_file_deploy_cycle()`              | Phase 2: 파일 단위 배포 및 JS 이동                 |
| **`core/file_utils`**     | `collect_files_for_FILE_from_P`        | 배포 대상 소스 파일(.xfdl, .xjs) 수집              |

---

## 2. 실행 흐름도 (Execution Flow)

```mermaid
flowchart TD
    subgraph Main_Logic [main.py]
        START([시작]) --> ARGS[인자 파싱]
        ARGS --> FIND_CFG[core.config_manager.find_geninfo_file]
        FIND_CFG --> TMP_XML[원본 폴더에 Geninfo.xml 복사]
        TMP_XML --> LOAD_CFG[core.config_manager.load_config_from_geninfo]
    end

    subgraph Sequence [Deployment Sequence]
        LOAD_CFG -- 2.1 ~ 2.3 --> CYCLE1[Cycle 1: -O 배포 및 파일 이동]
        CYCLE1 -- 2.4 ~ 2.6 --> CYCLE2[Cycle 2: -D 배포 및 파일 이동 (옵션)]
    end

    subgraph Cleanup [Cleanup & Exit]
        CYCLE2 --> TEST{--test 모드?}
        TEST -- Yes --> DEL_SUB[하위 작업 폴더라고만 삭제]
        DEL_SUB & TEST -- No --> FIN_DEL[Geninfo.xml 안전 삭제 (finally)]
        FIN_DEL --> END([종료])
    end
```

## 3. 리팩토링 및 고도화의 이점 (Advantages)

1.  **환경 독립적 실행 (Environment Agnostic)**:
    - `find_geninfo_file`을 통해 넥사크로 스튜디오 외부 도구 등록 시 작업 디렉토리 설정과 무관하게 설정 파일을 찾아 로드할 수 있습니다.

2.  **보안 및 권한 이슈 해결**:
    - 임시 파일을 항상 원본 파일이 있는 폴더에 생성함으로써, 권한이 없는 디렉토리에서 실행될 때 발생하는 `PermissionError`를 원천 차단했습니다.

3.  **최적화된 배포 시퀀스**:
    - `-O`와 `-D` 사이클을 명확히 분리하고, Phase 1(구조)과 Phase 2(파일)를 결합하여 넥사크로 배포 엔진이 가장 안정적으로 동작하는 2.1~2.6 단계를 구현했습니다.

4.  **유지보수 효율 극대화**:
    - 모든 공통 기능이 `core` 모듈에 집약되어 있어, `main.py`와 `search.py`가 동일한 로직을 공유하며 코드 수정을 한 번만으로 전체에 적용할 수 있습니다.
