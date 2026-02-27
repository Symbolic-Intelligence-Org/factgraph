"""
FactPy SDK 完整示例
==================
覆盖范围：
  1. Schema 定义（Entity / Identity / Field / 关联实体 / 维度字段 / 具化记录）
  2. SDKStore 初始化与 schema preflight
  3. 批量写入（sdk.batch）
  4. 数据读取（sdk.get / sdk.find / EntitySnapshot）
  5. 数据编辑（sdk.edit）
  6. 外部导入（sdk.ingest）
  7. 规则查询（sdk.run / Rule / RuleRef）
  8. 推导与接受（sdk.evaluate / sdk.accept / Derivation）
  9. 来源校验（sdk.validate_provenance）
 10. 错误处理
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 1. Schema 定义
# ---------------------------------------------------------------------------
from factpy_kernel.sdk import (
    Entity,
    Field,
    Identity,
    SDKStore,
    Rule,
    RuleRef,
    Derivation,
    Pred,
    Not,
    vars,
    schema_preflight_from_classes,
    EntityNotFoundError,
    FrozenSnapshotError,
    CardinalityError,
    EditorClosedError,
    SDKSchemaError,
    SDKStoreError,
    SDKDSLError,
)


class Country(Entity):
    """国家：复合自然键身份。"""
    source_system: str = Identity()
    source_id: str = Identity()

    name: str = Field(cardinality="functional", pred_id="country:name")
    population: int = Field(cardinality="functional", pred_id="country:population")


class Language(Entity):
    """语言：复合自然键身份。"""
    source_system: str = Identity()
    source_id: str = Identity()

    label: str = Field(cardinality="functional", pred_id="language:label")


class User(Entity):
    """用户：复合自然键身份，name 为 multi（允许别名），country 为函数式外键。"""
    source_system: str = Identity()
    source_id: str = Identity()

    name: str = Field(cardinality="multi", pred_id="user:name")
    country: Country = Field(cardinality="functional", pred_id="user:country")
    age: int = Field(cardinality="functional", pred_id="user:age")
    score: float = Field(cardinality="functional", pred_id="user:score")


class HasLanguage(Entity):
    """国家-语言关联。"""
    source_system: str = Identity()
    source_id: str = Identity()

    country: Country = Field(cardinality="functional", pred_id="haslang:country")
    language: Language = Field(cardinality="functional", pred_id="haslang:language")


class LivesIn(Entity):
    """居住记录（具化记录，自动生成 UUID 主键）。"""

    class Meta:
        is_record = True

    uid: str = Identity(default_factory="uuid4")

    user: User = Field(cardinality="functional", pred_id="livesin:user")
    country: Country = Field(cardinality="functional", pred_id="livesin:country")
    since: int = Field(cardinality="functional", pred_id="livesin:since")


class Speaks(Entity):
    """用户-语言能力（推导目标实体）。"""

    class Meta:
        is_record = True

    uid: str = Identity(default_factory="uuid4")

    user: User = Field(cardinality="functional", pred_id="speaks:user")
    language: Language = Field(cardinality="functional", pred_id="speaks:language")


# ---------------------------------------------------------------------------
# 2. SDKStore 初始化与 schema preflight
# ---------------------------------------------------------------------------

# 2a. Preflight（可在 CI 阶段或模块导入时执行，不依赖 SDKStore）
preflight = schema_preflight_from_classes(
    [Country, Language, User, HasLanguage, LivesIn, Speaks]
)
assert preflight["ok"], f"Schema preflight failed: {preflight.get('errors')}"
print("[preflight] schema ok, warnings:", preflight.get("warnings", []))

# 2b. 创建 SDKStore（schema 编译发生在此）
sdk = SDKStore.from_schema_classes(
    [Country, Language, User, HasLanguage, LivesIn, Speaks]
)
print("[init] SDKStore ready")

# ---------------------------------------------------------------------------
# 3. 批量写入（sdk.batch）
# ---------------------------------------------------------------------------

# 3a. 写入国家 & 语言基础数据
with sdk.batch(meta={"trace_id": "seed-001", "source": "ISO"}) as tx:
    de = tx.entity(Country, source_system="ISO3166", source_id="DE")
    de.name.set("Germany")
    de.population.set(83_000_000)

    fr = tx.entity(Country, source_system="ISO3166", source_id="FR")
    fr.name.set("France")
    fr.population.set(68_000_000)

    de_lang = tx.entity(Language, source_system="ISO639", source_id="deu")
    de_lang.label.set("German")

    fr_lang = tx.entity(Language, source_system="ISO639", source_id="fra")
    fr_lang.label.set("French")

    # 预览：read-only，可重复调用
    plan = tx.preview()
    print(f"[batch] {len(plan.ops)} ops staged")

    tx.commit()

# 3b. 写入用户及关联
with sdk.batch(meta={"trace_id": "users-001", "source": "HR"}) as tx:
    alice = tx.entity(User, source_system="APP", source_id="u-001")
    alice.name.add("Alice")
    alice.country.set(fr)   # 传入 handle 自动解析 entity_ref
    alice.age.set(30)
    alice.score.set(9.5)

    bob = tx.entity(User, source_system="APP", source_id="u-002")
    bob.name.add("Bob")
    bob.country.set(de)
    bob.age.set(25)
    bob.score.set(8.0)

    tx.commit()

# 3c. 写入居住记录（具化记录，uid 自动生成）
with sdk.batch(meta={"trace_id": "livesin-001"}) as tx:
    li_alice = tx.entity(LivesIn)   # uid 由 default_factory="uuid4" 生成
    li_alice.user.set(alice)
    li_alice.country.set(fr)
    li_alice.since.set(2020)

    li_bob = tx.entity(LivesIn)
    li_bob.user.set(bob)
    li_bob.country.set(de)
    li_bob.since.set(2018)

    tx.commit()

# 3d. 写入国家-语言关联
with sdk.batch(meta={"trace_id": "haslang-001"}) as tx:
    hl_fr = tx.entity(HasLanguage, source_system="APP", source_id="hl-fr-fra")
    hl_fr.country.set(fr)
    hl_fr.language.set(fr_lang)

    hl_de = tx.entity(HasLanguage, source_system="APP", source_id="hl-de-deu")
    hl_de.country.set(de)
    hl_de.language.set(de_lang)

    tx.commit()

print("[batch] all seed data written")

# ---------------------------------------------------------------------------
# 4. 数据读取
# ---------------------------------------------------------------------------

# 4a. sdk.get —— 精确身份查询
alice_snap = sdk.get(User, source_system="APP", source_id="u-001")
assert alice_snap is not None
print(f"[get] Alice snap: {alice_snap}")
print(f"  ref            = {alice_snap.ref}")
print(f"  age            = {alice_snap.age}")
print(f"  score          = {alice_snap.score}")
print(f"  identity       = {alice_snap.identity}")

# 4b. assertions 访问
name_assertions = alice_snap.assertions.name
print(f"  name active    = {[r.value for r in name_assertions.active]}")
print(f"  name history   = {[r.value for r in name_assertions.history]}")

country_assertions = alice_snap.assertions.country
chosen = country_assertions.chosen
print(f"  country chosen = {chosen.value if chosen else None}")

# 4c. 不存在时返回 None
missing = sdk.get(User, source_system="APP", source_id="u-999")
assert missing is None

# 4d. sdk.find —— 字段过滤
rows_age_30 = sdk.find(User, age=30)
print(f"[find] age=30 count: {len(rows_age_30)}")

rows_all = sdk.find(User)
print(f"[find] all users count: {len(rows_all)}")

rows_limit = sdk.find(User, limit=1)
print(f"[find] limit=1 count: {len(rows_limit)}")

# 4e. temporal_view="current"（仅当前有效 assertion）
rows_current = sdk.find(User, temporal_view="current")
print(f"[find] temporal_view=current count: {len(rows_current)}")

# ---------------------------------------------------------------------------
# 5. 数据编辑（sdk.edit）
# ---------------------------------------------------------------------------

# 5a. 上下文管理器（正常退出时自动 commit）
with sdk.edit(User, source_system="APP", source_id="u-001") as user_ed:
    user_ed.name.add("Alicia")   # 添加别名
    user_ed.age.set(31)

# 验证修改
alice_snap2 = sdk.get(User, source_system="APP", source_id="u-001")
assert alice_snap2 is not None
print(f"[edit] Alice names: {alice_snap2.assertions.name.active}")
print(f"[edit] Alice age:   {alice_snap2.age}")

# 5b. retract by asrt_id
alice_name_recs = alice_snap2.assertions.name.active
if len(alice_name_recs) >= 2:
    old_asrt_id = alice_name_recs[0].asrt_id
    with sdk.edit(User, source_system="APP", source_id="u-001") as user_ed:
        user_ed.name.retract(asrt_id=old_asrt_id)

# 5c. 手动 preview / commit / rollback
editor = sdk.edit(User, source_system="APP", source_id="u-001")
editor.__enter__()
try:
    editor.age.set(32)
    plan = editor.preview()
    print(f"[edit-manual] preview ops: {len(plan.ops)}")
    editor.commit(meta={"trace_id": "manual-fix"})
except Exception:
    editor.rollback()
    raise

# 5d. EntityNotFoundError
try:
    sdk.edit(User, source_system="APP", source_id="u-999")
except EntityNotFoundError as exc:
    print(f"[error] EntityNotFoundError: {exc}")

# ---------------------------------------------------------------------------
# 6. 外部导入（sdk.ingest）
# ---------------------------------------------------------------------------

alice_ref = sdk.ref(User, source_system="APP", source_id="u-001")
fr_ref = sdk.ref(Country, source_system="ISO3166", source_id="FR")

result = sdk.ingest(
    [
        {"kind": "add", "field": User.name, "e_ref": alice_ref, "value": "Ali"},
        {"kind": "set", "field": User.country, "e_ref": alice_ref, "value": fr_ref},
    ],
    meta={"source": "CSV_IMPORT", "trace_id": "import-2026-01"},
)
print(f"[ingest] written={result.written_assertion_ids}")
print(f"[ingest] skipped={result.skipped_count} dup={result.duplicate_count}")
for w in result.warnings:
    print(f"  [warn] {w['code']}: {w['message']}")
for d in result.diagnostics:
    print(f"  [diag] {d['severity']} {d['code']}: {d['message']}")

# 6b. ingest retract
alice_snap3 = sdk.get(User, source_system="APP", source_id="u-001")
if alice_snap3 and alice_snap3.assertions.name.active:
    target_asrt = alice_snap3.assertions.name.active[-1].asrt_id
    sdk.ingest(
        [{"kind": "retract", "asrt_id": target_asrt}],
        meta={"source": "CLEANUP"},
    )
    print(f"[ingest] retracted asrt_id={target_asrt}")

# 6c. 错误诊断示例（e_ref 缺失）
bad_result = sdk.ingest(
    [{"kind": "set", "field": User.age, "e_ref": "", "value": 99}],
)
for d in bad_result.diagnostics:
    print(f"[ingest-error] {d['severity']} {d['code']} @ {d['path']}: {d['message']}")

# ---------------------------------------------------------------------------
# 7. 规则查询（sdk.run / Rule）
# ---------------------------------------------------------------------------

# 7a. 简单规则：查询所有居住记录的 user -> country 对
with vars("li", "u", "c") as (li, u, c):
    livesin_rule = Rule(
        id="q.livesin",
        version="1.0.0",
        select=[u, c],
        where=[
            LivesIn(li),
            LivesIn.user(li=li, value=u),
            LivesIn.country(li=li, value=c),
        ],
    )

rows = sdk.run(livesin_rule)
print(f"[rule] livesin rows: {rows}")

# 7b. 规则引用（RuleRef）——可嵌套复用已标记为 expose=True 的规则
with vars("li", "u", "c") as (li, u, c):
    exposed_livesin = Rule(
        id="q.livesin.exposed",
        version="1.0.0",
        select=[u, c],
        expose=True,
        where=[
            LivesIn(li),
            LivesIn.user(li=li, value=u),
            LivesIn.country(li=li, value=c),
        ],
    )

with vars("u", "c") as (u, c):
    ref_rule = Rule(
        id="q.livesin.via_ref",
        version="1.0.0",
        select=[u, c],
        where=[
            RuleRef(exposed_livesin, u, c),
        ],
    )

rows_ref = sdk.run(ref_rule)
print(f"[rule-ref] livesin via ref: {rows_ref}")

# ---------------------------------------------------------------------------
# 8. 推导与接受（sdk.evaluate / sdk.accept / Derivation）
# ---------------------------------------------------------------------------

# 推导：若用户居住在国家 C，且国家 C 使用语言 L，则该用户会说语言 L
with vars("u", "l", "li", "hl", "c") as (u, l, li, hl, c):
    speaks_drv = Derivation(
        id="drv.speaks",
        version="1.0.0",
        where=[
            LivesIn(li),
            LivesIn.user(li=li, value=u),
            LivesIn.country(li=li, value=c),
            HasLanguage(hl),
            HasLanguage.country(hl=hl, value=c),
            HasLanguage.language(hl=hl, value=l),
        ],
        head=Speaks(user=u, language=l),
        materialize_as="record",
    )

cands = sdk.evaluate(speaks_drv)
print(f"[derive] candidate sets: {len(cands)}")

for cand in cands:
    # 可选：来源校验
    report = sdk.validate_provenance(cand, standard="derivation_v1")
    print(f"  provenance ok={report.ok} warnings={len(report.warnings)}")

    res = sdk.accept(cand, approved_by="pipeline")
    print(f"  accept: written={res.written_count} skipped={res.skipped_count}")

# 验证推导结果已写入
speaks_all = sdk.find(Speaks)
print(f"[derive] Speaks records: {len(speaks_all)}")

# ---------------------------------------------------------------------------
# 9. 来源校验（sdk.validate_provenance）
# ---------------------------------------------------------------------------

# 9a. 从 CandidateSet 校验（见第 8 节中的示例）

# 9b. 从 dict 校验（平面键形式）
prov_dict = {
    "derived_rule_id": "drv.speaks",
    "derived_rule_version": "1.0.0",
    "run_id": "run-abc-123",
    "support_kind": "python_in_memory",
    "support_digest": "sha256:" + "a" * 64,
}
report2 = sdk.validate_provenance(prov_dict, standard="derivation_v1")
print(f"[provenance] dict validate ok={report2.ok} errors={report2.errors}")

# 9c. 校验失败示例
bad_prov = {"derived_rule_id": "drv.x"}  # 缺少必填字段
bad_report = sdk.validate_provenance(bad_prov, standard="derivation_v1")
assert not bad_report.ok
print(f"[provenance] bad dict errors: {[e['code'] for e in bad_report.errors]}")

# ---------------------------------------------------------------------------
# 10. 错误处理示例
# ---------------------------------------------------------------------------

# 10a. FrozenSnapshotError
snap = sdk.get(User, source_system="APP", source_id="u-001")
try:
    snap.age = 99  # type: ignore[misc]
except FrozenSnapshotError as exc:
    print(f"[error] FrozenSnapshotError: {exc}")

# 10b. CardinalityError（multi 字段不能 set）
try:
    with sdk.edit(User, source_system="APP", source_id="u-001") as ed:
        ed.name.set("Wrong")   # name 是 multi，应用 add
except CardinalityError as exc:
    print(f"[error] CardinalityError: {exc}")

# 10c. EditorClosedError
editor2 = sdk.edit(User, source_system="APP", source_id="u-001")
editor2.__enter__()
editor2.commit()
try:
    editor2.age.set(99)
except EditorClosedError as exc:
    print(f"[error] EditorClosedError: {exc}")

# 10d. SDKSchemaError（get 传非身份字段）
try:
    sdk.get(User, source_system="APP", age=30)  # type: ignore[call-arg]
except SDKSchemaError as exc:
    print(f"[error] SDKSchemaError: {exc}")

# 10e. SDKDSLError（不支持的 DSL 构造）
try:
    with vars("x") as (x,):
        Rule(id="bad", version="1", select=[x], where=[])
except SDKDSLError as exc:
    print(f"[error] SDKDSLError: {exc}")

print("\n=== 示例运行完毕 ===")
