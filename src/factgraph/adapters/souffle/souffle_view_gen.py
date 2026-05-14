from __future__ import annotations

from factgraph.adapters.souffle.pred_norm import normalize_pred_id


def generate_view_dl(
    schema_ir: dict,
    *,
    include_active_rule: bool = True,
    include_witness_views: bool = False,
) -> str:
    if not isinstance(schema_ir, dict):
        raise TypeError("schema_ir must be dict")

    predicates = schema_ir.get("predicates")
    if not isinstance(predicates, list):
        raise ValueError("schema_ir.predicates must be list")

    lines: list[str] = [
        '.decl claim(Asrt:symbol, PredId:symbol, E:symbol, TupDigest:symbol)',
        '.decl claim_arg(Asrt:symbol, Idx:symbol, Val:symbol, Tag:symbol)',
        '.decl meta_time(Asrt:symbol, Key:symbol, EpochNanos:number)',
        '.decl revokes(Revoker:symbol, Revoked:symbol)',
        '.input claim',
        '.input claim_arg',
        '.input meta_time',
        '.input revokes',
        '',
    ]
    if include_active_rule:
        lines.extend(
            [
                '.decl active(A:symbol)',
                'active(A) :- claim(A,_,_,_), !revokes(_,A).',
                '',
            ]
        )

    for predicate in predicates:
        if not isinstance(predicate, dict):
            raise ValueError("schema predicate must be dict")

        pred_id = predicate.get("pred_id")
        cardinality = predicate.get("cardinality")
        arg_specs = predicate.get("arg_specs")
        group_key_indexes = predicate.get("group_key_indexes")

        if not isinstance(pred_id, str) or not pred_id:
            raise ValueError("predicate pred_id must be non-empty string")
        if cardinality not in {"single", "multi"}:
            raise NotImplementedError(
                f"souffle view generator supports only single/multi predicates: {pred_id}"
            )
        if not isinstance(arg_specs, list) or len(arg_specs) < 1:
            raise NotImplementedError(
                f"souffle view generator requires arg_specs length>=1 (E required): {pred_id}"
            )

        arg_count = len(arg_specs)
        normalized_group_indexes = _normalize_group_key_indexes(
            group_key_indexes, arg_count, pred_id
        )

        engine_pred = normalize_pred_id(pred_id)
        witness_pred = witness_rel_name(engine_pred)
        value_vars = [f"V{i}" for i in range(arg_count - 1)]
        output_decl_args = ["E:symbol", *[f"{var}:symbol" for var in value_vars]]
        lines.append(f'.decl {engine_pred}({", ".join(output_decl_args)})')
        lines.append(f'.output {engine_pred}')
        if include_witness_views:
            witness_decl_args = [*output_decl_args, "WA:symbol"]
            lines.append(f'.decl {witness_pred}({", ".join(witness_decl_args)})')

        output_head = f'{engine_pred}({", ".join(["E", *value_vars])})'
        if cardinality == "multi":
            output_body_parts = [
                f'claim(A,"{pred_id}",E,_)',
                "active(A)",
                *[
                    f'claim_arg(A,"{idx}",{value_var},TagOut{idx})'
                    for idx, value_var in enumerate(value_vars)
                ],
            ]
            lines.append(f'{output_head} :- {", ".join(output_body_parts)}.')
            if include_witness_views:
                witness_head = f'{witness_pred}({", ".join(["E", *value_vars, "A"])})'
                lines.append(f'{witness_head} :- {", ".join(output_body_parts)}.')
            lines.append("")
            continue

        dim_indexes = [index for index in normalized_group_indexes if index > 0]
        dim_vars = [f"D{i}" for i in range(len(dim_indexes))]

        cand_rel = f"cand__{engine_pred}"
        max_ts_rel = f"max_ts__{engine_pred}"
        chosen_rel = f"chosen_asrt__{engine_pred}"
        better_rel = f"better_asrt__{engine_pred}"

        cand_decl_args = ["A:symbol", "E:symbol", *[f"{var}:symbol" for var in dim_vars], "Ts:number"]
        lines.append(f'.decl {cand_rel}({", ".join(cand_decl_args)})')

        cand_body_parts = [
            f'claim(A,"{pred_id}",E,_)',
            'active(A)',
            'meta_time(A,"ingested_at",Ts)',
        ]
        for dim_position, arg_index in enumerate(dim_indexes):
            claim_idx = str(arg_index - 1)
            dim_var = dim_vars[dim_position]
            cand_body_parts.append(
                f'claim_arg(A,"{claim_idx}",{dim_var},TagDim{dim_position})'
            )
        lines.append(f'{cand_rel}(A,{", ".join(["E", *dim_vars, "Ts"])}) :- {", ".join(cand_body_parts)}.')
        lines.append('')

        max_decl_args = ["E:symbol", *[f"{var}:symbol" for var in dim_vars], "Ts:number"]
        lines.append(f'.decl {max_ts_rel}({", ".join(max_decl_args)})')
        key_vars = ["E", *dim_vars]
        key_args = ", ".join(key_vars)
        lines.append(
            f'{max_ts_rel}({", ".join([*key_vars, "Ts"])}) :- '
            f'{cand_rel}(_,{key_args},_), '
            f'Ts = max t : {{ {cand_rel}(_,{key_args},t) }}.'
        )
        lines.append('')

        better_decl_args = ["E:symbol", *[f"{var}:symbol" for var in dim_vars], "A:symbol"]
        lines.append(f'.decl {better_rel}({", ".join(better_decl_args)})')
        lines.append(
            f'{better_rel}({", ".join([*key_vars, "A"])}) :- '
            f'{cand_rel}(A,{", ".join([*key_vars, "Ts"])}), '
            f'{max_ts_rel}({", ".join([*key_vars, "Ts"])}), '
            f'{cand_rel}(B,{", ".join([*key_vars, "Ts"])}), B < A.'
        )
        lines.append('')

        chosen_decl_args = ["E:symbol", *[f"{var}:symbol" for var in dim_vars], "A:symbol"]
        lines.append(f'.decl {chosen_rel}({", ".join(chosen_decl_args)})')
        lines.append(
            f'{chosen_rel}({", ".join([*key_vars, "A"])}) :- '
            f'{cand_rel}(A,{", ".join([*key_vars, "Ts"])}), '
            f'{max_ts_rel}({", ".join([*key_vars, "Ts"])}), '
            f'!{better_rel}({", ".join([*key_vars, "A"])}).'
        )
        lines.append('')

        output_body_parts = [
            f'{chosen_rel}({", ".join([*key_vars, "A"])})',
            *[
                f'claim_arg(A,"{idx}",{value_var},TagOut{idx})'
                for idx, value_var in enumerate(value_vars)
            ],
        ]
        lines.append(f'{output_head} :- {", ".join(output_body_parts)}.')
        if include_witness_views:
            witness_head = f'{witness_pred}({", ".join(["E", *value_vars, "A"])})'
            lines.append(f'{witness_head} :- {", ".join(output_body_parts)}.')
        lines.append('')

    return "\n".join(lines).rstrip() + "\n"


def witness_rel_name(engine_pred: str) -> str:
    if not isinstance(engine_pred, str) or not engine_pred:
        raise ValueError("engine_pred must be non-empty string")
    return f"{engine_pred}_w"


def _normalize_group_key_indexes(
    raw_group_key_indexes: object,
    arg_count: int,
    pred_id: str,
) -> list[int]:
    if not isinstance(raw_group_key_indexes, list):
        raise NotImplementedError(
            f"souffle view generator requires list group_key_indexes: {pred_id}"
        )

    out: list[int] = []
    last = -1
    for index, raw_value in enumerate(raw_group_key_indexes):
        if isinstance(raw_value, bool) or not isinstance(raw_value, int):
            raise NotImplementedError(
                f"group_key_indexes[{index}] must be int for {pred_id}"
            )
        if raw_value < 0 or raw_value >= arg_count:
            raise NotImplementedError(
                f"group_key_indexes[{index}] out of range for {pred_id}"
            )
        if raw_value <= last:
            raise NotImplementedError(
                f"group_key_indexes must be strict ascending for {pred_id}"
            )
        out.append(raw_value)
        last = raw_value

    if 0 not in out:
        raise NotImplementedError(
            f"group_key_indexes must include 0 for {pred_id}"
        )

    return out


__all__ = ["generate_view_dl", "witness_rel_name"]
