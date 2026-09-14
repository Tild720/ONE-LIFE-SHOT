# Pistol 기본 전투

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
