# 러너 진행 단계와 끝 지점 스폰

## 맵 배치

`/Game/ThirdPerson/Lvl_ThirdPerson`의 Outliner `Runner` 폴더:

- `Runner_StartPoint`: (-10, -410, 50), 시작 기준 TargetPoint.
- `Runner_EndPoint`: (-10, 18070, 50), 종료 기준 TargetPoint.
- `Runner_ProgressManager`: 진행률과 공용 Enum 상태 관리.
- `Runner_EndSpawn_1` ~ `Runner_EndSpawn_4`: Y=17650, Z=150, X=-460/-160/140/440의 가로 4개 지점.
- 기존 시작 부근의 1회성 `BP_EnemyRunnerSpawner` 배치 2개를 이 끝쪽 4개 지점으로 교체했다. 기존 Blueprint 에셋 자체는 유지한다.

PlayerStart는 시작 지점 위 (-10, -410, 150)에 배치했다. 진행축은 +Y, 시작~끝 길이는 18,480cm이다. 기준점과 매니저·스폰 지점은 World Partition에서 항상 로드되도록 설정했다.

## 다른 Blueprint에서 진행 단계 사용

Enum 에셋: `/Game/Runner/E_RunnerStage`.
매니저: `/Game/Runner/BP_RunnerProgress`.

`Get Actor Of Class(BP_RunnerProgress)`로 참조를 얻어 보관하거나 에디터에서 참조를 지정한다. 참조 유효성을 확인한 뒤 다음 값을 읽는다.

- `CurrentStage`: E_RunnerStage. `Switch on E_RunnerStage`로 분기한다.
- `Progress`: 0~1 진행률.
- `RemainingDistance`: 끝까지 남은 길이 방향 거리(cm).
- `TrackLength`: 시작~끝 거리(cm).
- `OnStageChanged`: 단계가 실제 바뀔 때 한 번 호출하는 Event Dispatcher. 바인딩한 이벤트에서 `CurrentStage`를 읽는다.

진행률은 `(Player-Start)·(End-Start) / |End-Start|²`를 0~1로 제한한다. 좌우 이동에는 변하지 않는다. 현재 위치 기준이므로 뒤로 이동하면 이전 단계로 돌아가며, Complete에서 뒤로 나오면 스폰도 다시 허용된다. 별도의 승리/맵 전환 기능은 추가하지 않았다.

매니저의 `MiddleThreshold`, `LateThreshold`, `FinalThreshold`를 수정할 수 있다. `0 < Middle < Late < Final < 1` 순서를 유지한다. `UpdateInterval` 기본값은 0.2초이며 실제 타이머 주기는 0.05~1초로 제한한다. StartPoint/EndPoint가 없거나 길이가 1cm 이하이면 계산하지 않는다.

## 스폰 튜닝

각 `Runner_EndSpawn_*`는 기존 `/Game/Enemies/BP_EnemySpawnPoint`를 재사용한다. Details의 `Runner` 항목에서 단계별 클래스 배열과 간격을 조정한다.

| 단계 | 진행률 | 기본 적 풀 | 지점별 간격 |
|---|---|---|---|
| Early | 0~25% 미만 | Slow | 6초 |
| Middle | 25~50% 미만 | Slow, 기본 Runner | 4.5초 |
| Late | 50~75% 미만 | 기본 Runner, Fast | 3초 |
| Final | 75~100% 미만 | Fast | 1.5초 |
| Complete | 100% | 추가 스폰 없음 | — |

조정 변수:

- `ProgressManager`: 해당 맵의 매니저 참조. 없으면 스폰하지 않는다.
- `EarlyEnemyPool` / `MiddleEnemyPool` / `LateEnemyPool` / `FinalEnemyPool`: Actor 클래스 배열. 매번 배열에서 무작위 선택한다. 새 적 Blueprint를 이 배열에 추가하면 된다. 빈 배열·잘못된 클래스는 스폰을 건너뛴다.
- `EarlyInterval` / `MiddleInterval` / `LateInterval` / `FinalInterval`: 초 단위. 실제 간격은 0.1~3600초로 제한한다.
- `SpawnDelay`: 최초 지연. 배치 기본값은 0.2/0.5/0.8/1.1초로 분산했다.
- `Enabled`: 스폰 허용.
- `MaxAliveEnemies`: 지점별 유효한 생성 액터 수 상한, 기본 6. 사망 애니메이션 재생 중인 액터는 제거될 때까지 포함된다.
- `EnemyLifetime`: 생성 적의 최대 생존 시간, 기본 90초. 0이면 자동 수명 제한 없음.

0.2초 타이머로 상태를 확인한다. 생성 시도 후 다음 시간을 예약하며, 더 빠른 단계로 바뀌면 남은 대기를 새 간격 이하로 줄인다. 생성 위치가 막혔으면 강제로 겹쳐 생성하지 않고 다음 간격에 재시도한다. 각 지점의 AliveEnemies 목록은 생성 시도 때 유효한 액터만 유지한다. 기존 `SpawnSpeed` 변수는 호환성을 위해 남겼지만 단계별 생성에서는 사용하지 않는다.

## 적 외형·속도·피격

- 기존 `BP_EnemyStraightRunner`의 이동/사망 로직을 재사용한다. 스폰 시 플레이어 방향을 한 번 기록하며 이후 추적 방향을 갱신하지 않는다.
- 기본 Runner `MoveSpeed=400`, 자식 `BP_EnemyRunnerSlow=250`, `BP_EnemyRunnerFast=650` (cm/s). 해당 Blueprint의 Class Defaults에서 변경한다.
- 실제 렌더링 메시도 플레이어와 같은 `SKM_Dummy`, 크기 0.72. 재질은 `/Game/Enemies/Materials/M_EnemyRed`이며 `EnemyTint` 파라미터로 색을 조정한다.
- 달리기는 기존 `A_Dummy_Run`, 사망은 프로젝트의 KayKit General FBX에서 가져온 `Rig_Medium_General_Death_A`를 사용한다. 플레이어의 원본 애니메이션 에셋은 수정하지 않았다.
- `BP_BulletProjectile`의 Collision을 프로젝트의 `Bullet` 오브젝트 채널로 맞추고 Pawn과 Overlap하도록 수정했다. Runner와 겹치면 `Die`를 호출하고 탄을 제거한다. 기존 지형 Hit 처리와 총구 초기 속도/소유자 무시 로직은 유지한다.

## 카메라

`BP_ThirdPersonCharacter`의 SpringArm: Pitch=-55, Yaw=90, Absolute Rotation=true, Pawn Control Rotation=false, TargetOffset=(0,180,0). 기존 직교 카메라와 마우스 조준 입력은 유지한다.

## 검증 방법

1. Lvl_ThirdPerson을 열고 Play: PlayerStart에서 시작하고 맵이 화면 위쪽으로 곧게 이어지는지 확인.
2. PIE에서 Runner_ProgressManager를 선택해 Progress/CurrentStage를 확인. 길이의 25%, 50%, 75%, 끝에서 단계가 바뀌는지 확인.
3. 각 EndSpawn의 단계별 풀과 간격을 변경하여 다른 적이 생성되는지 확인. Complete에서는 추가 생성이 없어야 한다.
4. 플레이어와 동일한 형태의 빨간 적이 직선으로 이동하는지, 실제 탄에 맞으면 사망 애니메이션 후 제거되는지 확인.
5. Blueprint 컴파일 및 PIE 자동 점검: 경계값 0/25/50/75/100%, 범위 밖 clamp, 좌우 이동 불변, 4개 지점의 클래스 풀/속도/소유자, Complete 추가 생성 차단, Bullet 충돌 후 Dead와 제거 수명을 검사했다.

변경 에셋은 Runner 폴더의 Enum/매니저, Enemies의 스폰 Blueprint·기본/자식 적·붉은 재질·사망 애니메이션, 플레이어 카메라 Blueprint, Pistol 탄 Blueprint, Lvl_ThirdPerson의 외부 액터 배치다. 생성 캐시/Saved/Intermediate 파일은 작업 결과에 포함하지 않는다.
