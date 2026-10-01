# Pistol 기본 전투

## 한 발 전투 폴리싱 (2026-09-30)

앞뒤 이동은 유지한다. 이동의 목적은 빈 총 상태에서 적을 피하고 다음 사격 위치를 잡는 것이다. 원거리 처치 후 시체까지 걸어가는 공백은 적의 무기를 회수하는 짧은 시간으로 바꿨다.

- **카메라:** 기존 Character의 SpringArm을 Pitch=-55, Yaw=90, ArmLength=1400으로 고정했다. 조준 회전에 따라 카메라 위치가 돌던 가로 RelativeLocation을 0으로 수정했다. Collision Test를 꺼 벽 근처에서 카메라 거리가 갑자기 줄지 않는다.
- **처치 후 회수:** 기존 `BP_EnemyStraightRunner.Die`가 기존 `BP_PistolPickup`을 한 번 생성하고 `ReturnToPlayer`를 호출한다. 기본 0.55초 동안 현재 플레이어 위치로 이동하며, 도착 후 실제 획득에 성공해야 새 Pistol의 한 발을 얻는다. 비행 중에는 Ammo=0을 유지한다.
- **획득 안전장치:** 기존 Pickup의 `TryAcquire`를 오버랩과 타이머가 공유한다. 이미 한 발이 있으면 총과 Pickup을 보존한다. 동시에 여러 무기가 돌아와도 하나만 장착하며 나머지는 근처에 남는다. 사망한 플레이어는 획득하지 못한다. 일반 바닥 Pickup은 접근해서 획득한다.
- **첫 전투:** 기존 `Runner_EndSpawn_1/2`를 Y=1500/1900으로 옮겼다. SpawnDelay=2/3.5초, Interval=4초, MaxAliveEnemies=각 2, Slow Runner를 사용한다. 기존 SpawnSpeed를 사용할 수 있는 선택 옵션을 추가하고 이 두 배치에만 300을 적용했다. 다른 스포너는 기본 동작을 유지한다.
- **피드백:** 기존 HUD에 `READY`, `EMPTY`, `DOWN` 상태와 조작 안내를 표시한다. 적 접촉은 `Character.FailRun`을 호출해 입력·이동·충돌을 중단하고 짧은 화면 페이드 후 기본 0.55초에 레벨을 다시 연다. R로 즉시 다시 시도할 수도 있다.
- **Editor 조정값:** Pickup의 `ReturnDuration`, `PickupRadius`; Character의 `RetryDelay`; SpawnPoint의 `UseSpawnSpeedOverride`, `SpawnSpeed`와 기존 스폰 간격/수량.

### 변경한 기존 에셋

- `/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter`, `BP_AmmoHUD`
- `/Game/Weapons/Pistol/BP_Pistol`, `BP_PistolPickup`
- `/Game/Enemies/BP_EnemyStraightRunner`, `BP_EnemySpawnPoint`
- `/Game/ThirdPerson/Lvl_ThirdPerson`과 기존 배치 액터의 World Partition 외부 파일

### 확인 방법

1. `Lvl_ThirdPerson`에서 Play하고 시작 Pickup에 접근한다. HUD `1/1`을 확인한다.
2. 적을 맞춰 처치한다. 발사 직후 `0/1`, 무기 비행, 도착 후 `1/1`을 순서대로 확인한다. 허공에 쏘면 추가 발사가 되지 않는다.
3. 마우스를 사방으로 움직이고 벽 옆에서 이동한다. 카메라 방향과 거리가 유지되는지 확인한다.
4. 접근하는 적에게 닿으면 `DOWN`과 페이드 뒤 초기 Pickup 및 `0/1` 상태로 재시작하는지 확인한다.

`Tools/Test-OneShotLoop.py`는 실제 Fire/Die/TryAcquire 호출로 단발 소모, 중복 사망, 비행 중 빈 총, 도착 후 획득, 장전 중 Pickup 보존, 동시 회수를 확인한다. `Tools/Test-OneShotCamera.py`는 PIE에서 캐릭터 회전·벽 위치·앞뒤 이동·사망·레벨 재시작 후 카메라 및 상태를 확인한다. 결과 파일은 각각 `Saved/OneShotLoopTest.json`, `Saved/OneShotCameraTest.json`이다. 테스트용 Python 호출은 플레이용 Blueprint에 저장하지 않는다.

현재 구현 범위는 Pistol 전투 흐름이다. Shotgun/Sniper/RPG, 5개 시설 스테이지와 최종 클리어 흐름은 아직 완성되지 않았다.

## 이전 한 발 전투 검증 기록 (2026-09-30)

- `BP_Pistol.UnlimitedAmmo=false`: 획득한 Pistol은 한 발만 발사한다. 발사가 성공하면 Ammo가 0이 되고, 빈 총은 다음 Pickup을 얻을 때까지 손에 남는다.
- 기존 `BP_ThirdPersonCharacter.EquipPistol`은 장착한 Pistol의 Ammo가 0일 때만 이전 총을 버리고 새 총을 장착한다. Ammo가 1이면 Pickup을 소비하지 않는다.
- `BP_EnemyStraightRunner.Die`: 중복 사망 방지 후 기존 `BP_PistolPickup`을 사망 위치에 한 번 생성한다. Slow/Fast 자식 적도 이 동작을 상속한다.
- `BP_EnemyStraightRunner.WeaponMesh`는 기존 `Gun_Pistol` 메시를 `WeaponSocket_R`에 붙이고 충돌을 끈다. 적이 쓰던 무기와 처치 후 떨어지는 무기가 일치하며, 자식 Runner도 상속한다.
- 기존 `BP_AmmoHUD.AmmoLabel`은 시작 시 `0/1`, Pistol 획득 시 `1/1`, 발사 시 `0/1`로 바뀐다. Pickup과 Pistol의 기존 이벤트에서만 갱신한다.
- `Lvl_ThirdPerson` 시작 구간의 `Runner_IntroEnemy`는 기존 `BP_EnemyStraightRunner`를 사용하며 MoveSpeed=0인 첫 사격 대상이다.
- `BP_ThirdPersonPlayerController`의 R 키는 현재 레벨 이름으로 `OpenLevel`을 호출해 한 발을 빗맞혔을 때 즉시 다시 시도하게 한다. 아직 전투 구역별 체크포인트가 없어 레벨 시작점으로 돌아간다.
- 적 `OnActorHit`의 기존 탄환 판별이 실패하면 충돌 액터가 플레이어인지 확인한다. 플레이어와 접촉한 경우 현재 레벨을 즉시 다시 연다. 실험용으로 첫 적의 MoveSpeed를 550으로 높여 충돌 후 레벨 재로드를 확인하고, 원래 값 0으로 되돌렸다.
- UE 5.8 PIE에서 초기 Pickup 획득(Ammo 1), 발사 후 Ammo 0, 적 처치 후 Pickup 생성, 재획득(새 Pistol Ammo 1)을 확인했다. 별도 임시 Pickup으로 Ammo 0 상태의 즉시 교체도 확인한 뒤 임시 액터를 제거했다. HUD 값은 0/1 → 1/1 → 0/1로 확인했다.
- PIE에서 R 입력 후 플레이어가 시작점으로 돌아가고 초기 Pickup 및 HUD 0/1이 복원되는 것을 확인했다.
- `Tools/Test-Pistol.py`는 이제 세 번 입력 시 실제 이동하는 탄이 정확히 하나만 생기는지 확인한다. PIE에서 초기 Pickup을 획득한 뒤 실행한다.

아래의 무한 탄약 테스트 모드와 `Inf/inf` HUD 설명은 이전 기록이며, 현재 동작에는 이 절을 우선한다.

## 잔광 시작점 및 명중 조각·탄피 (2026-09-16)

- BP_BulletProjectile: 시작 잔광 길이 0. BeginPlay에서 위치를 기록하고, 실제 이동 거리까지 길이를 늘린다. MaxTrailLength=220에 도달하면 Actor Tick을 끈다. 따라서 발사 직후 총 뒤로 잔광이 튀어나오지 않는다.
- BP_PistolImpactBits: 확인된 타깃 명중 위치에서 발광 네모 조각 8개를 배출한다. BurstSpeed=170, SpreadSpeed=100, 수명 0.45초. 엔진 Cube와 기존 M_BulletTracer를 재사용한다. 물리로 퍼지지만 다른 물체와 충돌하지 않는 장식 효과이며 Niagara 시스템은 아니다.
- BP_PistolCasing / M_PistolCasing: 발사마다 황동색 원통 탄피 1개를 총 옆의 로컬 좌표 (10,25,15)에서 배출한다. EjectionSpeed=170, 위쪽 속도 140, 회전 후 중력으로 떨어지고 0.7초 후 제거한다. 충돌·게임플레이 영향은 없다.
- Tools/Test-PistolCosmetics.py: PIE에서 총 획득 후 실행. 약 2.4초간 입력을 잠시 막고 테스트한 뒤 복원한다. 기존 테스트용 총알/조각/탄피를 정리하므로 일반 플레이 도중에는 실행하지 않는다. Saved/PistolCosmeticsTest.json에 잔광 범위, 조각·탄피 생성과 제거 결과를 기록한다.

이 절의 잔광 동작이 아래의 고정 길이 설명보다 우선한다.

## 발사 피드백과 HUD (2026-09-16)

- 바닥처럼 수평인 표면을 조준할 때 총구 높이의 평면 교점을 사용해 수평 발사한다. 세로 표면(타깃/벽)은 실제 Trace 명중점을 향하며 충돌 시 총알을 제거한다.
- Bullet 수명은 6초, 속도 2200. 장애물이 없으면 최대 약 13,200유닛 이동한다. Tracer 길이 220, 두께 3.5. 충돌 때문에 사라지는 동작은 유지한다.
- CS_PistolFire: 0.18초, 위치 진폭 4, 주파수 32. CS_PistolHit: 0.12초, 진폭 5, 주파수 45. 회전/FOV는 흔들지 않는다.
- BP_Pistol: MuzzleLightIntensity=6000, MuzzleLightDuration=0.10초. 총구 옆의 그림자 없는 주황색 Point Light가 발사 후 자동으로 꺼진다. 재발사하면 타이머를 다시 시작한다.
- BP_TargetActor: HitFlashDuration=0.16초. 실제 Bullet 명중 시 M_TargetHitFlash 빨간 Overlay Material을 잠시 적용하고 제거한다. 원래 머티리얼은 보존한다.
- /Game/ThirdPerson/Blueprints/BP_AmmoHUD: 오른쪽 아래 짙은 반투명 패널과 청록색 강조선, PISTOL / AMMO / Inf/inf 표시. 기존 BP_ThirdPersonGameMode의 HUD Class로 연결했다. HUDMargin, AmmoLabel을 Editor에서 조절한다. AmmoLabel은 요청한 테스트용 고정 표시이며 실제 탄약 연동은 하지 않는다.
- 검증: PIE에서 총 획득 후 Tools/Test-PistolFeedback.py 실행. 총알 수평 이동 1500유닛 이상, 발사광 켜짐/꺼짐, 타깃 점멸/복원, HUD 생성 여부를 Saved/PistolFeedbackTest.json에 기록한다. 발사/명중 Shake 클래스도 기록한다.

최신 설정은 이 절이 우선한다.

## 현재 테스트 모드 (2026-09-15)

- `BP_Pistol.UnlimitedAmmo=true`: 좌클릭할 때마다 한 발씩 반복 발사한다. 자동 연사는 아니다. false로 바꾸면 아래의 기존 1발 규칙을 사용한다.
- 마우스 Trace가 빗나가도 총구 높이의 평면과 커서 광선의 교점을 사용해서 발사한다. 충돌 지점이 있을 때는 기존 Hit 위치를 사용한다.
- Character `WeaponGripOffset.Scale=0.75`, PickupMesh Scale=0.75. 손의 본 스케일 보정을 포함한 장착 총의 실제 월드 Scale은 0.54이다.
- BulletMesh Scale=1.0, Collision Radius=4, ProjectileSpeed=2200. 기본 수명 3초와 충돌 시 제거를 유지한다.
- `BP_BulletProjectile.Tracer`: 엔진 Cylinder 메시를 총알 뒤에 붙인 길이 100, 두께 2.5의 발광 표시. 충돌과 그림자는 없다. 곡선 이동 이력을 남기는 Niagara 리본은 아니며 직선 총알의 시인성용이다.
- `/Game/Weapons/Pistol/M_BulletTracer`: Unlit 발광 머티리얼. TracerColor로 색을 바꿀 수 있다. Tracer 컴포넌트의 Transform으로 길이와 두께를 조정한다.
- 재현 확인: 빈 공간 조준 시 수정 전 생성 0개, 수정 후 1개. Enhanced Input으로 세 번 발사해 서로 다른 세 총알의 이동을 확인했고, Target 두 번 타격 로그도 확인했다.
- 재검증 스크립트: PIE에서 Pistol 획득 후 Unreal Python으로 `Tools/Test-Pistol.py`를 실행한다. 결과는 `Saved/PistolTest.json` 및 Output Log에 출력한다.

이하 문서는 최초 1발 전투 구현의 설명이며, 위 테스트 모드 설정이 우선한다.

PROJECT.md는 저장소에서 찾지 못해 현재 Unreal/MCP 정보를 기준으로 작업했다. 기존 Third Person Character, 이동, 고정 쿼터뷰 및 마우스 방향 캐릭터 회전을 재사용한다.

## 생성 에셋
- /Game/Weapons/Pistol/BP_Pistol: WeaponMesh, Ammo=1, Fire 함수. 성공적으로 Projectile이 생성된 경우에만 Ammo=0. 추가 클릭은 무시한다.
- /Game/Weapons/Pistol/BP_PistolPickup: PickupRadius 기본 130. Pawn 오버랩으로 기존 Character.EquipPistol 호출 후 획득 성공 시 제거한다. 이미 장착 중이면 교체하지 않는다.
- /Game/Weapons/Pistol/BP_BulletProjectile: 반경 3 Sphere, ProjectileMovement, ProjectileSpeed 기본 3500, 중력 0, 수명 3초. 자기 Pawn과 소유 Pistol을 이동 충돌에서 제외한다. 블로킹 충돌 시 제거한다.
- /Game/Weapons/Pistol/BP_TargetActor: TargetMesh와 PistolTarget 태그. 파괴/체력/AI 없음.
- /Game/Weapons/Pistol/CS_PistolFire: 위치 흔들림, 0.12초, 진폭 1.2, 주파수 35.
- /Game/Weapons/Pistol/CS_PistolHit: 위치 흔들림, 0.07초, 진폭 0.8, 주파수 55.
- /Game/Input/Actions/IA_Fire: Bool 입력, Started에서 한 번 발사한다.

## 수정 에셋과 실제 메시
- /Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter: EquippedPistol, WeaponGripOffset, EquipPistol 함수, IA_Fire 처리 추가.
- /Game/Input/IMC_Default: IA_Fire에 LeftMouseButton 매핑 추가.
- /Game/Characters/KayKit/Meshes/SKM_Dummy: WeaponSocket_R 생성. 실제 handslot_r 본에 연결. 본의 100배 스케일을 소켓 Scale 0.01로 보정. 회전 Pitch -75, Yaw 90, Roll 90.
- /Game/Characters/KayKit/Assets/fbx/Gun_Pistol: Muzzle 소켓. 위치 (0,71,12), 회전 Yaw 90. 실제 메시의 총구 쪽 정점과 범위를 확인하여 설정.
- /Game/Characters/KayKit/Assets/fbx/Bullet: 기존 Bullet 메시 사용.
- /Game/Characters/KayKit/Assets/fbx/target: 기존 소문자 target 메시 사용. 필요한 단순 충돌 확인/생성.
- /Game/ThirdPerson/Lvl_ThirdPerson: Pistol Pickup (180,-105,75), Pistol Target (350,160,140) 배치. World Partition 외부 Actor 파일에 저장.

Gun_Pistol_Magazine은 /Game/Characters/KayKit/Assets/fbx/Gun_Pistol_Magazine에서 확인했으며 Reload가 없으므로 이번 기능에는 연결하지 않았다.

## Editor 조정값
- BP_PistolPickup: PickupRadius.
- Character: WeaponGripOffset (기본 Scale 0.45), WeaponSocket_R의 위치/회전. 소켓 Scale 0.01은 가져온 본의 스케일 보정값이다.
- Gun_Pistol Static Mesh Editor: Muzzle 위치/회전.
- BP_BulletProjectile: ProjectileSpeed, Sphere Radius, Initial Life Span.
- BP_Pistol / Bullet: FireShakeScale / HitShakeScale.
- CS_PistolFire / CS_PistolHit: Oscillation Duration, Loc Oscillation Amplitude/Frequency.
- FireSound, HitSound, MuzzleEffect, ImpactEffect는 비어 있으며 실제 에셋을 지정하면 연결된 재생 호출을 사용한다. 새 VFX/SFX를 생성하거나 다운로드하지 않았다.

## 조준과 충돌
마우스를 Deproject하고 Visibility 채널로 월드 Trace한다. 자기 Pawn과 Pistol을 제외한 첫 충돌점에 대해 Muzzle에서 LookAt 방향을 구해 Bullet을 생성한다. Trace에 실패하면 발사하지 않으며 탄약도 소모하지 않는다. 바닥뿐 아니라 직접 커서를 올린 Target에도 조준할 수 있다. 총구 위치는 플레이어 중심과 분리되어 있다.
카메라 셰이크는 위치만 아주 작게 흔들며 회전/FOV 진동은 사용하지 않는다.

## 테스트
1. Lvl_ThirdPerson에서 Play. 시작 위치에서 W 방향으로 조금 이동해 근처 Pistol Pickup에 접근한다.
2. Pickup이 없어지고 오른손에 Pistol이 붙는지 확인한다.
3. Target에 마우스를 올리고 좌클릭한다. 총구에서 한 발이 발사되고 발사 셰이크가 발생한다.
4. Target 충돌 시 Bullet이 없어지고 Hit 셰이크 및 Output Log의 Pistol Target Hit를 확인한다. Target은 남는다.
5. 다시 좌클릭해도 발사되지 않는다. 다시 테스트할 때는 Play를 종료하고 시작한다.

## 검증
Blueprint 컴파일/저장 및 패키지 재로드 통과. 새 PIE에서 이동 입력으로 자동 획득, WeaponSocket_R 부착, Ammo 1, 장착 총 월드 Scale 0.324를 확인했다. 첫 발에서 Ammo 0 및 Target Hit 로그, 이후 Bullet 0/Target 1을 확인했다. PlayerCameraManager에 Fire/Hit 셰이크 인스턴스가 각각 생성됐다. 두 번째 클릭은 추가 발사하지 않았다.
