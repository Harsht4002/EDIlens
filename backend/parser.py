"""Richer flat X12 parser with practical delimiter/rule handling."""

from typing import Any


def parse_edi(raw: str, complete_parse: bool = False) -> dict[str, Any]:
    """Parse raw X12 text into flat segments and basic validation errors."""
    segments: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    raw = (raw or "").strip()
    if not raw:
        return {"segments": segments, "errors": errors, "meta": {}}

    delimiters = _detect_delimiters(raw)
    segment_strings = _split_segments(raw, delimiters["segment_separator"])

    for index, seg_str in enumerate(segment_strings):
        parts = seg_str.split(delimiters["element_separator"])
        parts = [p.strip() for p in parts]
        if not parts or not parts[0]:
            continue

        segment_name = parts[0].strip()
        elements = parts[1:]
        parsed_elements = [_parse_element_value(v, delimiters["component_separator"]) for v in elements]

        segment_data: dict[str, Any] = {
            "index": index,
            "segment": segment_name,
            "elements": elements,
            "parsedElements": parsed_elements,
            "interpreted": _interpret_segment(segment_name, elements, parsed_elements),
            "raw": seg_str,
        }

        segment_errors = _check_segment_errors(segment_name, elements, index)
        if segment_errors:
            segment_data["error"] = "; ".join(segment_errors)
            for err in segment_errors:
                errors.append({"segment": segment_name, "index": index, "error": err, "raw": seg_str})

        segments.append(segment_data)

    _append_envelope_errors(segments, errors)

    result: dict[str, Any] = {"segments": segments, "errors": errors, "meta": delimiters}
    if complete_parse:
        result["complete"] = _build_complete_parse(segments, delimiters, errors)
    return result


def _detect_delimiters(raw: str) -> dict[str, str]:
    # X12 ISA usually defines: element separator at index 3, segment terminator at index 105.
    element_separator = "*"
    component_separator = ":"
    segment_separator = "~"

    if raw.startswith("ISA") and len(raw) > 106:
        element_separator = raw[3]
        segment_separator = raw[105]
        if len(raw) > 104:
            component_separator = raw[104]

    if not segment_separator.strip():
        segment_separator = "~"

    return {
        "element_separator": element_separator,
        "component_separator": component_separator,
        "segment_separator": segment_separator,
    }


def _split_segments(raw: str, segment_separator: str) -> list[str]:
    normalized = raw.replace("\r\n", "\n").replace("\r", "\n")
    if segment_separator in normalized:
        return [s.strip() for s in normalized.split(segment_separator) if s.strip()]
    # Fallback for malformed files that are line-separated.
    return [s.strip() for s in normalized.split("\n") if s.strip()]


def _parse_element_value(value: str, component_separator: str) -> Any:
    if component_separator and component_separator in value:
        return [v for v in value.split(component_separator)]
    return value


def _check_segment_errors(segment_name: str, elements: list[str], index: int) -> list[str]:
    issues: list[str] = []
    if len(elements) < 1 and segment_name not in {"SE", "GE", "IEA"}:
        issues.append("Segment has too few elements")

    # Minimal practical numeric checks by segment + element index (1-based after segment name).
    numeric_rules: dict[str, list[int]] = {
        "SE": [1],      # Included segment count
        "GE": [1],      # Number of transaction sets
        "IEA": [1],     # Number of functional groups
        "HL": [1, 2],   # HL01, HL02
        "CLM": [2],     # Claim amount
        "SV1": [2],     # Professional service line charge amount
    }

    for pos in numeric_rules.get(segment_name, []):
        idx = pos - 1
        if idx < len(elements) and elements[idx]:
            value = elements[idx]
            try:
                float(value.replace(",", ""))
            except ValueError:
                issues.append(f"Invalid number format at element {pos}: '{value}'")

    if len(segment_name) < 2 or len(segment_name) > 3:
        issues.append(f"Unexpected segment identifier '{segment_name}' at index {index}")

    return issues


def _append_envelope_errors(segments: list[dict[str, Any]], errors: list[dict[str, Any]]) -> None:
    st_count = sum(1 for s in segments if s["segment"] == "ST")
    se_count = sum(1 for s in segments if s["segment"] == "SE")
    gs_count = sum(1 for s in segments if s["segment"] == "GS")
    ge_count = sum(1 for s in segments if s["segment"] == "GE")

    if st_count != se_count:
        errors.append({"segment": "SE", "error": f"ST/SE count mismatch: ST={st_count}, SE={se_count}"})
    if gs_count != ge_count:
        errors.append({"segment": "GE", "error": f"GS/GE count mismatch: GS={gs_count}, GE={ge_count}"})

    # Validate ST/SE transaction counts when both exist.
    st_indices = [i for i, s in enumerate(segments) if s["segment"] == "ST"]
    se_indices = [i for i, s in enumerate(segments) if s["segment"] == "SE"]
    for pair_idx, st_i in enumerate(st_indices):
        if pair_idx >= len(se_indices):
            break
        se_i = se_indices[pair_idx]
        if se_i <= st_i:
            errors.append({"segment": "SE", "error": "SE appears before its matching ST"})
            continue
        expected = segments[se_i]["elements"][0] if segments[se_i]["elements"] else ""
        try:
            expected_count = int(float(expected))
        except ValueError:
            continue
        actual_count = se_i - st_i + 1
        if expected_count != actual_count:
            errors.append(
                {
                    "segment": "SE",
                    "error": f"SE01 segment count mismatch: expected {expected_count}, actual {actual_count}",
                    "index": se_i,
                }
            )


def _get(values: list[Any], index: int, default: str = "") -> Any:
    return values[index] if index < len(values) else default


def _interpret_segment(segment: str, elements: list[str], parsed_elements: list[Any]) -> dict[str, Any]:
    """
    Return a more readable segment-specific interpretation.
    This remains flat and additive so existing functionality is preserved.
    """
    # Generic fallback for unknown segments.
    generic = {"elementCount": len(elements)}

    if segment == "ISA":
        return {
            "authorizationQualifier": _get(elements, 0),
            "authorizationInfo": _get(elements, 1),
            "securityQualifier": _get(elements, 2),
            "securityInfo": _get(elements, 3),
            "senderQualifier": _get(elements, 4),
            "senderId": _get(elements, 5),
            "receiverQualifier": _get(elements, 6),
            "receiverId": _get(elements, 7),
            "interchangeDate": _get(elements, 8),
            "interchangeTime": _get(elements, 9),
            "repetitionSeparator": _get(elements, 10),
            "version": _get(elements, 11),
            "controlNumber": _get(elements, 12),
            "ackRequested": _get(elements, 13),
            "usageIndicator": _get(elements, 14),
            "componentSeparator": _get(elements, 15),
        }
    if segment == "GS":
        return {
            "functionalIdCode": _get(elements, 0),
            "applicationSenderCode": _get(elements, 1),
            "applicationReceiverCode": _get(elements, 2),
            "date": _get(elements, 3),
            "time": _get(elements, 4),
            "groupControlNumber": _get(elements, 5),
            "responsibleAgencyCode": _get(elements, 6),
            "version": _get(elements, 7),
        }
    if segment == "ST":
        return {
            "transactionSetId": _get(elements, 0),
            "controlNumber": _get(elements, 1),
            "implementationConventionRef": _get(elements, 2),
        }
    if segment == "BHT":
        return {
            "hierarchicalStructureCode": _get(elements, 0),
            "transactionSetPurposeCode": _get(elements, 1),
            "referenceId": _get(elements, 2),
            "date": _get(elements, 3),
            "time": _get(elements, 4),
            "transactionTypeCode": _get(elements, 5),
        }
    if segment in {"NM1", "N1"}:
        return {
            "entityIdentifierCode": _get(elements, 0),
            "entityTypeQualifier": _get(elements, 1),
            "lastOrOrgName": _get(elements, 2),
            "firstName": _get(elements, 3),
            "middleName": _get(elements, 4),
            "namePrefix": _get(elements, 5),
            "nameSuffix": _get(elements, 6),
            "idCodeQualifier": _get(elements, 7),
            "idCode": _get(elements, 8),
        }
    if segment == "PER":
        return {
            "contactFunctionCode": _get(elements, 0),
            "name": _get(elements, 1),
            "commNumberQualifier1": _get(elements, 2),
            "commNumber1": _get(elements, 3),
            "commNumberQualifier2": _get(elements, 4),
            "commNumber2": _get(elements, 5),
        }
    if segment == "HL":
        return {
            "hierarchicalIdNumber": _get(elements, 0),
            "parentIdNumber": _get(elements, 1),
            "levelCode": _get(elements, 2),
            "childCode": _get(elements, 3),
        }
    if segment == "SBR":
        return {
            "payerResponsibilityCode": _get(elements, 0),
            "individualRelationshipCode": _get(elements, 1),
            "groupPolicyNumber": _get(elements, 2),
            "groupName": _get(elements, 3),
            "insuranceTypeCode": _get(elements, 4),
            "coordinationOfBenefitsCode": _get(elements, 8),
        }
    if segment == "PAT":
        return {
            "individualRelationshipCode": _get(elements, 0),
            "patientLocationCode": _get(elements, 1),
            "employmentStatusCode": _get(elements, 4),
            "studentStatusCode": _get(elements, 5),
        }
    if segment in {"DMG", "DTP"}:
        return {
            "dateTimeQualifier": _get(elements, 0),
            "formatQualifier": _get(elements, 1),
            "value": _get(elements, 2),
        }
    if segment == "CLM":
        claim_freq = _get(parsed_elements, 4)
        return {
            "claimSubmitterId": _get(elements, 0),
            "totalClaimChargeAmount": _get(elements, 1),
            "placeOfServiceAndFrequency": claim_freq,
            "providerSignatureOnFile": _get(elements, 5),
            "assignmentParticipationCode": _get(elements, 6),
            "benefitsAssignmentCertification": _get(elements, 7),
            "releaseOfInfoCode": _get(elements, 8),
        }
    if segment == "HI":
        return {
            "diagnosisEntries": parsed_elements,
        }
    if segment == "SV1":
        return {
            "compositeMedicalProcedureIdentifier": _get(parsed_elements, 0),
            "lineItemChargeAmount": _get(elements, 1),
            "unitOrBasisForMeasurementCode": _get(elements, 2),
            "serviceUnitCount": _get(elements, 3),
            "placeOfServiceCode": _get(elements, 4),
            "diagnosisCodePointer": _get(elements, 6),
        }
    if segment == "LX":
        return {"assignedNumber": _get(elements, 0)}
    if segment == "SE":
        return {"includedSegmentCount": _get(elements, 0), "transactionSetControlNumber": _get(elements, 1)}
    if segment == "GE":
        return {"numberOfTransactionSets": _get(elements, 0), "groupControlNumber": _get(elements, 1)}
    if segment == "IEA":
        return {"numberOfFunctionalGroups": _get(elements, 0), "interchangeControlNumber": _get(elements, 1)}

    return generic


def _build_complete_parse(
    segments: list[dict[str, Any]], delimiters: dict[str, str], errors: list[dict[str, Any]]
) -> dict[str, Any]:
    """
    Build a deeper envelope/transaction representation while keeping base flat parse unchanged.
    """
    interchanges: list[dict[str, Any]] = []
    current_interchange: dict[str, Any] | None = None
    current_group: dict[str, Any] | None = None
    current_txn: dict[str, Any] | None = None

    for seg in segments:
        seg_id = seg["segment"]

        if seg_id == "ISA":
            if current_interchange:
                interchanges.append(current_interchange)
            current_interchange = {
                "header": seg,
                "functionalGroups": [],
                "trailer": None,
            }
            current_group = None
            current_txn = None
            continue

        if seg_id == "IEA":
            if not current_interchange:
                current_interchange = {"header": None, "functionalGroups": [], "trailer": seg}
            else:
                current_interchange["trailer"] = seg
            interchanges.append(current_interchange)
            current_interchange = None
            current_group = None
            current_txn = None
            continue

        if seg_id == "GS":
            if not current_interchange:
                current_interchange = {"header": None, "functionalGroups": [], "trailer": None}
            current_group = {
                "header": seg,
                "transactions": [],
                "trailer": None,
            }
            current_interchange["functionalGroups"].append(current_group)
            current_txn = None
            continue

        if seg_id == "GE":
            if current_group:
                current_group["trailer"] = seg
            current_group = None
            current_txn = None
            continue

        if seg_id == "ST":
            if not current_group:
                if not current_interchange:
                    current_interchange = {"header": None, "functionalGroups": [], "trailer": None}
                current_group = {"header": None, "transactions": [], "trailer": None}
                current_interchange["functionalGroups"].append(current_group)
            current_txn = {
                "header": seg,
                "segments": [],
                "loops": [],
                "trailer": None,
            }
            current_group["transactions"].append(current_txn)
            continue

        if seg_id == "SE":
            if current_txn:
                current_txn["trailer"] = seg
                current_txn["loops"] = _infer_hl_loops(current_txn["segments"])
                current_txn["tree"] = _build_transaction_tree(current_txn["segments"])
            current_txn = None
            continue

        if current_txn is not None:
            current_txn["segments"].append(seg)
        elif current_group is not None:
            # Group-level segment outside ST/SE.
            current_group.setdefault("segments", []).append(seg)
        elif current_interchange is not None:
            # Interchange-level segment outside GS/GE.
            current_interchange.setdefault("segments", []).append(seg)

    if current_interchange:
        interchanges.append(current_interchange)

    summary = {
        "interchangeCount": len(interchanges),
        "groupCount": sum(len(i.get("functionalGroups", [])) for i in interchanges),
        "transactionCount": sum(
            len(g.get("transactions", []))
            for i in interchanges
            for g in i.get("functionalGroups", [])
        ),
        "segmentCount": len(segments),
        "errorCount": len(errors),
    }

    return {
        "summary": summary,
        "delimiters": delimiters,
        "interchanges": interchanges,
    }


def _infer_hl_loops(txn_segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Infer a basic HL hierarchy for healthcare transactions.
    """
    loops: list[dict[str, Any]] = []
    loop_map: dict[str, dict[str, Any]] = {}
    current_loop: dict[str, Any] | None = None

    for seg in txn_segments:
        if seg["segment"] == "HL":
            hl01 = seg["elements"][0] if len(seg["elements"]) > 0 else ""
            hl02 = seg["elements"][1] if len(seg["elements"]) > 1 else ""
            hl03 = seg["elements"][2] if len(seg["elements"]) > 2 else ""

            loop_obj: dict[str, Any] = {
                "hlId": hl01,
                "parentHlId": hl02,
                "levelCode": hl03,
                "segment": seg,
                "segments": [],
                "children": [],
            }
            loops.append(loop_obj)
            if hl01:
                loop_map[hl01] = loop_obj
            if hl02 and hl02 in loop_map:
                loop_map[hl02]["children"].append(loop_obj)
            current_loop = loop_obj
        elif current_loop is not None:
            current_loop["segments"].append(seg)

    return loops


def _build_transaction_tree(txn_segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Build a practical hierarchical tree from flat transaction segments.
    Uses common 837-style anchors (HL/CLM/LX/NM1) but remains generic.
    """
    roots: list[dict[str, Any]] = []
    current_hl: dict[str, Any] | None = None
    current_claim: dict[str, Any] | None = None
    current_service: dict[str, Any] | None = None
    current_entity: dict[str, Any] | None = None

    for seg in txn_segments:
        seg_id = seg["segment"]

        if seg_id == "HL":
            node = {
                "type": "hlLoop",
                "segment": seg,
                "children": [],
                "claims": [],
                "entities": [],
                "otherSegments": [],
            }
            roots.append(node)
            current_hl = node
            current_claim = None
            current_service = None
            current_entity = None
            continue

        if seg_id == "CLM":
            node = {
                "type": "claimLoop",
                "segment": seg,
                "children": [],
                "diagnoses": [],
                "services": [],
                "entities": [],
                "otherSegments": [],
            }
            if current_hl is not None:
                current_hl["claims"].append(node)
            else:
                roots.append(node)
            current_claim = node
            current_service = None
            current_entity = None
            continue

        if seg_id == "LX":
            node = {
                "type": "serviceLoop",
                "segment": seg,
                "children": [],
                "serviceLines": [],
                "entities": [],
                "otherSegments": [],
            }
            if current_claim is not None:
                current_claim["services"].append(node)
            elif current_hl is not None:
                current_hl["children"].append(node)
            else:
                roots.append(node)
            current_service = node
            current_entity = None
            continue

        if seg_id in {"NM1", "N1"}:
            node = {
                "type": "entity",
                "segment": seg,
                "children": [],
                "otherSegments": [],
            }
            if current_service is not None:
                current_service["entities"].append(node)
            elif current_claim is not None:
                current_claim["entities"].append(node)
            elif current_hl is not None:
                current_hl["entities"].append(node)
            else:
                roots.append(node)
            current_entity = node
            continue

        if seg_id == "HI":
            if current_claim is not None:
                current_claim["diagnoses"].append(seg)
            else:
                _push_segment_to_best_bucket(roots, current_hl, current_claim, current_service, current_entity, seg)
            continue

        if seg_id in {"SV1", "SV2", "SV3"}:
            if current_service is not None:
                current_service["serviceLines"].append(seg)
            elif current_claim is not None:
                current_claim["otherSegments"].append(seg)
            else:
                _push_segment_to_best_bucket(roots, current_hl, current_claim, current_service, current_entity, seg)
            continue

        _push_segment_to_best_bucket(roots, current_hl, current_claim, current_service, current_entity, seg)

    return roots


def _push_segment_to_best_bucket(
    roots: list[dict[str, Any]],
    current_hl: dict[str, Any] | None,
    current_claim: dict[str, Any] | None,
    current_service: dict[str, Any] | None,
    current_entity: dict[str, Any] | None,
    seg: dict[str, Any],
) -> None:
    if current_entity is not None:
        current_entity["otherSegments"].append(seg)
    elif current_service is not None:
        current_service["otherSegments"].append(seg)
    elif current_claim is not None:
        current_claim["otherSegments"].append(seg)
    elif current_hl is not None:
        current_hl["otherSegments"].append(seg)
    else:
        roots.append({"type": "segment", "segment": seg})
