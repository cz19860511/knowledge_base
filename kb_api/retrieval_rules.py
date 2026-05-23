from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalRule:
    name: str
    trigger_terms: tuple[str, ...]
    expansion_terms: tuple[str, ...]
    boost_terms: tuple[str, ...]
    preferred_doc_types: tuple[str, ...] = ()
    preferred_folders: tuple[str, ...] = ()
    penalty_terms: tuple[str, ...] = ()


RULES: tuple[RetrievalRule, ...] = (
    RetrievalRule(
        name="hazmat_vehicle",
        trigger_terms=("危化", "危险化学", "危化品", "危化车辆"),
        expansion_terms=(
            "危险化学品",
            "危化品车辆",
            "危化车辆",
            "危险化学品运输车辆",
            "危险化学品停车区域",
            "危险化学品停车位",
            "定点停放",
            "危化品事故",
            "危化品泄露",
            "危化品泄漏",
            "应急预案",
            "组织救援",
            "现场处置",
            "报告",
            "安全要求",
        ),
        boost_terms=(
            "危险化学品",
            "危化品",
            "危化车辆",
            "危险化学品运输车辆",
            "危险化学品停车区域",
            "危险化学品停车位",
            "定点停放",
            "危化品事故",
            "危化品泄露",
            "危化品泄漏",
            "应急预案",
            "组织救援",
        ),
        preferred_doc_types=("安全应急", "SOP流程"),
        preferred_folders=("06安全与应急资料", "03SOP流程化资料"),
    ),
    RetrievalRule(
        name="traffic_congestion",
        trigger_terms=("拥堵", "堵车", "疏导", "停车秩序", "车流"),
        expansion_terms=(
            "停车秩序",
            "车辆疏导",
            "现场指挥",
            "车辆停靠",
            "车辆停放",
            "进出畅通",
            "停放整齐有序",
            "公共场区停车秩序",
            "停车场",
            "交通标识标线",
            "停车位",
        ),
        boost_terms=(
            "停车秩序",
            "现场指挥",
            "车辆停靠",
            "车辆停放",
            "进出畅通",
            "停放整齐有序",
            "公共场区",
            "停车位",
            "停车场",
            "交通标识标线",
        ),
        preferred_doc_types=("SOP流程", "岗位职责", "表单台账"),
        preferred_folders=("03SOP流程化资料", "04表单台账", "05岗位职责"),
    ),
    RetrievalRule(
        name="cashier_violation",
        trigger_terms=("违规收银", "收银违规", "合作收银", "收银监管", "私自收款", "非收银员"),
        expansion_terms=(
            "合作收银",
            "合作收银日常稽查",
            "收银监管",
            "电子支付",
            "店铺监管",
            "非收银员不得操作收银机",
            "授权密码",
            "不得上机收款",
            "上机收款",
            "诚信经营",
            "现场记录",
            "日常稽查",
        ),
        boost_terms=(
            "合作收银",
            "合作收银日常稽查",
            "收银监管",
            "非收银员不得操作收银机",
            "授权密码",
            "不得上机收款",
            "上机收款",
            "收银机",
            "电子支付",
            "店铺监管",
            "诚信经营",
        ),
        preferred_doc_types=("表单台账", "SOP流程", "岗位职责"),
        preferred_folders=("04表单台账", "03SOP流程化资料", "05岗位职责"),
        penalty_terms=("信息安全技术", "网络安全", "系统安全", "安全机制整合"),
    ),
    RetrievalRule(
        name="facility_inspection",
        trigger_terms=("设备设施巡检", "设施巡检", "设备巡检", "巡检要求", "维护保养", "设施设备"),
        expansion_terms=(
            "设备设施",
            "服务设施",
            "定期检测",
            "定期检查",
            "安全隐患",
            "巡回检查",
            "维护保养",
            "设施设备安全管理",
            "维修记录",
            "检查记录",
        ),
        boost_terms=(
            "设备设施",
            "服务设施",
            "定期检测",
            "定期检查",
            "安全隐患",
            "巡回检查",
            "维护保养",
            "设施设备安全管理",
            "维修记录",
            "检查记录",
        ),
        preferred_doc_types=("安全应急", "SOP流程", "岗位职责"),
        preferred_folders=("06安全与应急资料", "03SOP流程化资料", "05岗位职责"),
    ),
    RetrievalRule(
        name="fire_inspection",
        trigger_terms=("消防检查", "消防巡查", "消防安全", "消防"),
        expansion_terms=(
            "消防检查",
            "安全检查",
            "消防设施",
            "消防器材",
            "隐患整改",
            "巡回检查",
            "火灾事故",
            "义务消防队",
        ),
        boost_terms=(
            "消防检查",
            "安全检查",
            "消防设施",
            "消防器材",
            "隐患整改",
            "巡回检查",
            "火灾事故",
            "义务消防队",
        ),
        preferred_doc_types=("安全应急", "SOP流程"),
        preferred_folders=("06安全与应急资料", "03SOP流程化资料"),
    ),
)


def match_rules(query: str) -> list[RetrievalRule]:
    return [rule for rule in RULES if any(term in query for term in rule.trigger_terms)]


def expanded_query(query: str, rules: list[RetrievalRule]) -> str:
    if not rules:
        return query
    terms: list[str] = []
    seen: set[str] = set()
    for rule in rules:
        for term in rule.expansion_terms:
            if term not in seen:
                terms.append(term)
                seen.add(term)
    return query + " " + " ".join(terms)
