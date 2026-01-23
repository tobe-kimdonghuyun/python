# Nexacro 배포 자동화를 위한 Copilot 지침

## 프로젝트 개요
**Nexacro XML 기반 배포 자동화 도구**로 다음을 수행합니다:
1. `typedefinition.xml`을 파싱하여 `<Services>` 블록에서 상대 경로 토큰 추출
2. 추출된 토큰을 기반으로 배포 소스 파일(`.xfdl`, `.xjs`) 발견
3. Nexacro의 `nexacrodeploy.exe`를 2단계(프로젝트 레벨 → 파일 레벨)로 실행
4. 생성된 `.js` 출력 파일을 배포 디렉토리로 이동

**핵심 영역**: Nexacro 프레임워크 배포; XML 서비스 정의; 경로 토큰 추출 및 치환

## 아키텍처 & 모듈 책임

### 진입점: `main.py`
- 모듈들을 순서대로 호출하여 전체 워크플로우 조율
- CLI 인자 파싱 처리(`config_path`, `--run-deploy`, 인코딩 옵션 등)
- **주요 흐름**: 인자 파싱 → 설정 로드 → 기준 디렉토리 계산 → XML 파싱 → 경로 계산 → 단계별 실행

### 모듈: `core/config_manager.py`
- **목적**: 설정 파일 처리 및 경로 해석
- **핵심 함수**:
  - `load_config()`: `config.json`을 딕셔너리로 읽음; 파일 없거나 JSON 형식 오류 시 종료
  - `resolve_config_path_value()`: 설정 파일 디렉토리를 기준으로 상대 경로를 절대 경로로 변환
  - `get_required_config_value()`: 필수 설정 키 값 조회 및 검증; 없으면 종료
  - `get_base_dir_from_P()`: `-P`(프로젝트 .xprj 파일)를 사용하여 기준 디렉토리 결정

### 모듈: `core/xml_parser.py`
- **목적**: Nexacro XML 정의에서 상대 경로 토큰 추출
- **핵심 함수**: `search_rel_paths_in_services_block()`
  - `typedefinition.xml`의 `<Services>...</Services>` 블록 내에서만 검색
  - 패턴: `../`로 시작하고 공백/대괄호가 아닌 문자가 따르는 경로 (정규식: `\.\./[^\"'\s<>]+`)
  - `(exit_code, rel_paths_list)` 반환 (exit_code=0이면 경로 발견)
  - `--contains-only` 플래그 준수 (첫 발견 시 조기 반환)

### 모듈: `core/file_utils.py`
- **목적**: 파일 발견 및 경로 계산
- **핵심 함수**:
  - `compute_effective_O_values()`: 상대 경로를 기준 경로와 결합하여 절대 `-O`(출력) 경로로 매핑
  - `collect_files_for_FILE_from_P()`: `-P` 기준으로 디렉토리를 스캔하여 발견된 상대 경로와 일치하는 `.xfdl`, `.xjs` 파일 수집
  - `move_js_files_from_file_dir()`: 배포 후 생성된 `.js` 파일을 소스 디렉토리에서 `-O` 대상 디렉토리로 이동

### 모듈: `core/deploy_manager.py`
- **목적**: Nexacro 배포 명령 실행
- **핵심 함수**:
  - `build_deploy_base_command()`: 설정에서 기본 명령어 리스트 생성 (`nexacroDeployExecute`, `-P`, `-B`, 선택적 `-D`, `-COMPRESS`, `-SHRINK`)
  - `run_phase1_project_deploy()`: `-O`와 `-GENERATERULE`을 사용한 단일 전체 프로젝트 배포 실행
  - `run_phase2_file_deploy()`: 상대 경로별/파일별 반복; 각 조합에 대해 `-FILE` 파라미터로 배포 실행; 각 파일 후 `move_js_files_from_file_dir()` 호출
  - 서브프로세스 반환 오류 시 0이 아닌 코드로 종료

## 설정 형식 (`config.json`)

**필수 키** (`config_manager.get_required_config_value`에서 검증):
- `-P`: `.xprj` 프로젝트 파일 경로
- `-O`: 기본 출력/배포 대상 디렉토리
- `-B`: Nexacro SDK 라이브러리 디렉토리
- `-GENERATERULE`: 생성 규칙/템플릿 디렉토리 경로
- `nexacroDeployExecute`: `nexacrodeploy.exe` 경로

**선택적 키**:
- `-D`: 대체 출력 기준 (Phase 1에서만 `-O` 오버라이드)
- `-COMPRESS`: 불린값; true면 `-COMPRESS` 플래그 추가
- `-SHRINK`: 불린값; true면 `-SHRINK` 플래그 추가

**경로 처리**: 모든 경로는 상대 경로(설정 파일 위치 기준 해석) 또는 절대 경로 가능

## 주요 패턴 & 관례

### 2단계 배포 흐름
- **Phase 1** (`run_phase1_project_deploy`): 전체 프로젝트로 단일 실행 (전체 `-O` 경로 한 번 배포)
- **Phase 2** (`run_phase2_file_deploy`): 발견된 상대 경로별/소스 파일별 반복 실행
- 각 Phase 2 반복: 배포 실행 `→` `.js` 결과 이동

### 상대 경로 토큰 추출
- **XML 내**: `<Services>` 태그 내에서만 검색 (정규식을 사용한 상태 기반 라인별 파싱)
- **토큰 형식**: `../some/path` (문자 `../` 접두어, 토큰을 끝내는 따옴표/괄호 없음)
- **중복 제거**: `seen_targets` 집합으로 같은 경로 중복 처리 방지

### 파일 수집 전략
- `.xfdl`(XML UI 폼)과 `.xjs`(JavaScript 스크립트) 파일만 배포 소스
- 확장자 대소문자 무시 (`.lower()` 사용)
- 상대 경로가 파일을 가리킴: 허용 확장자면 포함; 디렉토리: 일치 파일 스캔

### 오류 처리 전략
- 설정 검증 오류 및 파일 누락: 메시지 출력, `sys.exit(2)` 호출
- 서브프로세스 배포 실패: 오류 출력, 서브프로세스 반환 코드로 `sys.exit()` 호출
- 우아한 경로 해석: `os.path.normpath()`로 정규화

## 테스트 & 디버깅

### 테스트용 CLI 옵션
- `--test`: 정상 실행 후 생성 파일 삭제 (안전한 테스트 모드)
- `--contains-only`: 경로 토큰 존재 확인 후 즉시 종료 (빠른 검증)
- `--max-hits N`: 검색 결과를 N개로 제한 (성능 튜닝)
- `--encoding`, `--errors`: XML 파싱 인코딩 문제 디버깅

### 일반적인 디버깅 포인트
1. **XML을 찾을 수 없음**: 설정의 `-P` 값 확인; `get_base_dir_from_P()`의 기준 디렉토리 계산 확인
2. **경로가 추출되지 않음**: XML에 `<Services>` 태그 존재 확인; `xml_parser.py`의 정규식 패턴 확인
3. **파일이 배포되지 않음**: 계산된 디렉토리에 `.xfdl`, `.xjs` 파일 존재 확인 (`collect_files_for_FILE_from_P()` 로직 확인)
4. **서브프로세스 실패**: `nexacrodeploy.exe` 경로 및 `build_deploy_base_command()`의 명령어 생성 검토

## 실행 파일 빌드

PyInstaller로 독립형 `.exe` 생성:
```bash
python -m PyInstaller --onefile --noconfirm --clean -n search search.py
```
또는 Nuitka로 최적화 바이너리 생성:
```bash
py -OO -m nuitka --standalone --onefile main.py --product-name="Deploy Tool"
```

## 통합 지점 & 의존성

- **외부 실행 파일**: `nexacrodeploy.exe` (Nexacro 플랫폼 도구; 설정의 경로)
- **파일 형식 의존성**: `typedefinition.xml` (Nexacro 서비스 레지스트리), `.xprj` (프로젝트 파일)
- **타사 Python 패키지 없음**: 표준 라이브러리만 사용 (`argparse`, `os`, `json`, `subprocess`, `re`, `shutil`)

---

**마지막 수정**: 2026-01-24  
**리팩토링 구조**: 모놀리식 `search.py`에서의 마이그레이션 이유는 `refactored_structure_and_flow.md` 참고
