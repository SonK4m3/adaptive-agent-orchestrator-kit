# Agent graph / Codex orchestrator improvement plan

Ngày lập: 2026-10-01, Asia/Saigon (+07:00).
Trạng thái: local implementation partially complete; Phase 1–2 complete, Phase 3 runtime gate blocked. Phase 4 harness/fixtures implemented but live runs deferred; Phase 5 deferred behind the gate. Phase 5 resource pilot vẫn cần quyết định riêng. Xem docs/validation/AGENT-GRAPH-IMPLEMENTATION-2026-10-01.md.

## Mục tiêu và ranh giới

Cải thiện độ tin cậy khi root chọn, vận hành và điều chỉnh đội agent theo task của user. Ưu tiên: đúng/đủ yêu cầu, thời gian, rồi usage. Giữ adaptive L0–L3, role nền ổn định với expertise theo task, một writer/path, verification theo rủi ro, root sở hữu integration và completion claims.

Không xây workflow engine, dashboard hay hệ thống billing. Không đổi model mặc định/global settings, cài vào dự án khác, commit/push hoặc chạy benchmark diện rộng trong plan này. Không biến nhiều file thành điều kiện bắt buộc spawn. Không coi Mermaid hoặc TOML là runtime evidence.

Nguồn: guides/ORCHESTRATION-POLICY.md; guides/UPSTREAM-COMPARISON.md; skills/adaptive-agent-orchestrator/; profiles/adaptive/; eval/scenarios/; eval/rubrics/orchestration.md; docs/validation/ORCHESTRATION-RUN-2026-10-01.md.

Baseline hiện có: bốn scenario đều L0; named roles, ownership handoff và reuse chưa được kiểm chứng. Các thay đổi repo đang có là baseline cần bảo toàn, không phải nội dung được phép reset.

## Cách tổ chức triển khai

Root giữ thiết kế/schema, runner và integration. Đầu việc nhỏ/tightly coupled làm L0. Có thể giao một agent read-only review schema hoặc protocol nếu tạo đầu ra độc lập; packet phải chỉ rõ yêu cầu, file đọc, deliverable và checkpoint. Không spawn để đáp ứng plan. Không cho writer song song sửa hai alias của cùng policy; một owner cập nhật cả hai.

Mỗi phase có ledger acceptance, evidence và kết luận riêng. Task completion và orchestration handling là hai kết quả khác nhau: phát hiện blocker đúng không đồng nghĩa hoàn thành task. Unrun/unknown không được ghi pass. Chỉ chuyển phase khi gate trước được đáp ứng hoặc ghi rõ phần độc lập được phép tiếp tục.

## Phase 1 — Sửa navigation và contract drift

Write scope:
- skills/{adaptive-agent-orchestrator,astra-orchestrator}/references/{roles,evaluation}.md
- scripts/validate_package.py
- tests/test_release.py hoặc tests/test_validate_package.py (mới, nếu cần)

Việc làm: thay hướng dẫn install-roles.ps1 không tồn tại bằng CLI installer hiện có; sửa scenario catalog reference; bỏ claim concurrency riêng của một máy khỏi tài liệu portable. Đổi navigation nội bộ phù hợp thành Markdown links kiểm chứng được, nhưng không tạo dependency khiến skill cài riêng bị hỏng. Hướng dẫn chạy repo-level CLI phải nêu rõ cần source checkout/package, không giả định script nằm trong installed skill.

Acceptance:
- P1.1 Hướng dẫn cài roles có command/path tồn tại và đúng arguments hiện có.
- P1.2 Catalog navigation đúng ở source; installed skill không có link hỏng tới ngoài bundle.
- P1.3 Hai alias vẫn có policy/resources tương đương.
- P1.4 Có regression check cho navigation sửa ở phase này; không cố kiểm tra mọi plain-text path bằng regex rộng.

Evidence: diff, validator, focused regression test và kiểm tra link trên bản skill cài riêng. Gate: không còn tham chiếu cũ đã xác định; không đổi routing hay model.

## Phase 2 — Chuẩn hóa graph record tối giản

Write scope:
- skills/{adaptive-agent-orchestrator,astra-orchestrator}/SKILL.md
- skills/{adaptive-agent-orchestrator,astra-orchestrator}/assets/{task-contract,delegation-contract,run-record}.md
- skills/{adaptive-agent-orchestrator,astra-orchestrator}/references/{patterns,evaluation}.md
- eval/rubrics/orchestration.md
- guides/ORCHESTRATION-POLICY.md
- eval/fixtures/graph-record/ (mới), scripts/validate_graph_record.py (mới), tests/test_graph_record.py (mới)

Thiết kế: node là workstream với đầu ra kiểm chứng được; agent là assignee, không đồng nhất với node. Có graph revision, workstream ID, requirement IDs, expertise/role, concrete output, dependencies, read/write scope, implementation owner, verification owner/method, assignee ID hoặc root, status và evidence pointers. Edge phân biệt dependency và verification. L0 có một node/root, không cần child giả.

Trạng thái node: pending, running, blocked, completed, cancelled. Ledger criterion giữ pending/pass/fail/unrun/blocked riêng. Replan ghi delta: trigger, revision cũ/mới, scope/owner thay đổi, obsolete work disposition. Ownership transfer yêu cầu evidence agent cũ đã dừng/hoàn tất hoặc handoff được xác nhận trước writer mới; yêu cầu stop không phải bằng chứng đã stop.

Không bắt mỗi task ghi mọi tool call. Dùng bản record ngắn, JSON snapshot khi cần kiểm tra cơ học; không dựng state engine hay suy diễn lifecycle từ prose. Thống nhất vocabulary với task-retro-survey bằng mapping/reference, không copy toàn bộ survey schema vào orchestrator.

Acceptance:
- P2.1 Represent được L0, hai workstream độc lập, verification độc lập và blocker/reassignment.
- P2.2 Mỗi criterion có implementation owner, verification owner, phương pháp và evidence/status riêng.
- P2.3 Validator phát hiện ID/dependency không tồn tại, cycle dependency, exclusive write ownership trùng và completed thiếu evidence pointer; không giả vờ xác minh nội dung bằng chứng.
- P2.4 Scope ownership được chuẩn hóa theo workspace; đọc chung hợp lệ, hai writer đang active cùng path không hợp lệ. Kiểm tra chỉ trong phạm vi path/schema hỗ trợ, không claim OS isolation.
- P2.5 Revision/handoff không thể coi request stop là confirmed stop; có negative fixtures.
- P2.6 Packet/record đủ gọn để không bắt root lặp lại toàn bộ chat; hai alias đồng bộ.

Evidence: positive/negative fixtures, unit tests, một record mẫu mỗi case. Gate: schema/contracts/rubric nhất quán và deterministic tests pass; chưa claim agent thực sự tuân thủ.

## Phase 3 — Kiểm chứng runtime dispatch/profile

Write scope:
- scripts/run_orchestration.py
- scripts/runtime_probe.py (mới, nếu cần)
- tests/test_run_orchestration.py (mới)
- guides/PROFILES.md
- docs/validation/AGENT-DISPATCH-<date>.md (mới)
- profiles/*/codex/config.toml chỉ khi probe xác định lỗi schema; không đổi role model pins ở phase này.

Việc làm: kiểm tra installed CLI/tool schema hiện có; chọn một runtime đích cho vòng đầu, ưu tiên CLI nếu fixture automation khả dụng. Cài package vào temporary CODEX_HOME, không sửa cấu hình user. Probe phải dùng preset/roles đang kiểm chứng, không ignore chúng như runner policy hiện tại. Ghi CLI version, profile resolution, roles exposed và configured/requested/confirmed resources riêng. Không gửi source thật ra ngoài.

Hai probe đầu: một named worker hoàn thành bounded fixture và external oracle; một named read-only reviewer trả assessment độc lập. Đây là forced plumbing tests, không chấm routing. Ghi agent ID, spawn/send/wait/close thực tế và lifecycle; fallback default không được ghi named-role pass. Chỉ claim concurrency khi trace thực sự xác nhận; capacity enforcement chưa đo giữ unverified.

Acceptance:
- P3.1 Temporary config/profile được runtime đọc; exposed role hoặc lỗi thiếu role có evidence.
- P3.2 Có real named worker dispatch, artifact trong scope, external check pass và lifecycle closure.
- P3.3 Reviewer không viết production files; assessment có references tới yêu cầu/artifact và không nhận implementer confidence trước.
- P3.4 Timeout/dispatch failure được ghi incomplete/fail, không pass theo exit code; cancellation xử lý descendants theo runtime hỗ trợ.
- P3.5 Config user trước/sau không đổi; không suy diễn effective model nếu runtime không attests.

Gate: worker/reviewer plumbing pass trên runtime đích. Nếu unsupported, báo blocker cụ thể; không tự đổi global config để vượt gate. Có thể tiếp tục hoàn thiện fixture Phase 4, nhưng không claim role/profile đã hoạt động.

## Phase 4 — Kiểm chứng chọn graph và adaptation

Write scope:
- eval/scenarios/{catalog,orchestration}.md
- eval/rubrics/orchestration.md
- eval/fixtures/graph-behavior/ (mới)
- eval/oracles/graph-behavior/ (mới)
- scripts/run_orchestration.py, tests/test_run_orchestration.py
- docs/validation/AGENT-GRAPH-RUN-<date>.md (mới)

Chuẩn bị bốn scenario:
1. Bounded edit: root-only có lý do hợp lý, không spawn thừa.
2. Workstream độc lập đủ substantive: hai đầu ra/interfaces rõ và external integration oracle; nhiều topology vẫn hợp lệ.
3. Auth boundary có regression/negative cases: đánh giá nhu cầu verification độc lập, reviewer/tester contribution và fallback trung thực.
4. Mid-run requirement/blocker: inject trigger được timestamp sau checkpoint quan sát được; kiểm tra contract revision, stop/handoff/reuse và affected acceptance. Harness không inject được thì ghi adaptation untested, không thay bằng blocker từ đầu.

Không reveal expected topology/rubric vào user prompt. Scope exact paths và acceptance public; oracle của evaluator ở ngoài write scope. Phân biệt coverage không được exercise với lỗi hành vi; không ép spawn để lấy đủ điểm. Graph decision không spawn vẫn có thể đúng, nhưng chưa chứng minh delegation lifecycle.

Acceptance:
- P4.1 Mỗi run có outcomes từng criterion, scope diff/hash, raw trace và graph revisions liên kết được.
- P4.2 Hard failure làm orchestration run fail bất kể điểm diagnostic; timeout incomplete; blocker đúng ghi task blocked.
- P4.3 Verification owner là actor; command/suite là phương pháp, không phải owner.
- P4.4 Adaptation outcome dựa trên observed trigger và tool/artifact evidence; không chỉ final prose.
- P4.5 Có ít nhất một autonomous run với real useful delegation để claim routing/delegation đã exercise. Nếu không xảy ra, báo coverage gap và xem lại scenario, không chuyển sang ép topology rồi gọi là autonomous pass.

Gate: báo cáo rõ exercised/unexercised/failed dimensions và xử lý material failures trước Phase 5. Một run/scenario là evidence ban đầu, không reliability rate.

## Phase 5 — Tinh gọn policy rồi mới thử resource economy

Write scope:
- skills/{adaptive-agent-orchestrator,astra-orchestrator}/SKILL.md
- skills/{adaptive-agent-orchestrator,astra-orchestrator}/references/{patterns,roles,model-deadline}.md
- profiles/ descriptors/config hoặc role variants chỉ theo thiết kế được duyệt
- scripts/validate_package.py, tests/ tương ứng
- docs/validation/ORCHESTRATOR-ECONOMY-<date>.md (mới)

Đợt A: gộp đoạn reassessment lặp; short decision guide và lazy-load đúng pattern; giữ self-contained aliases. Không đồng thời đổi model/effort. Kiểm tra mọi mandatory rule vẫn có nguồn duy nhất hoặc navigation rõ.

Đợt B, được duyệt riêng: chọn một bounded scenario đã có baseline, so effort hiện tại với candidate thấp hơn được runtime hỗ trợ. Giữ spec/revision/tools/oracle, root model và topology protocol cố định; chỉ đổi yếu tố muốn đo. Ghi actual graph khác nhau như confound, không giấu chúng. Không mặc định hạ effort cho security/design/review.

Acceptance:
- P5.1 Scope/ownership/replan/verification/hard-failure/authority rules không bị mất khi rút gọn.
- P5.2 Named role pin và runtime capability được kiểm tra trước resource experiment.
- P5.3 So quality trước latency/usage; include retry/failure/review cost. Unknown metrics giữ unknown.
- P5.4 Account usage %, task tokens, API dollars và subscription credits tách riêng; không suy ra chi phí task từ một snapshot account.
- P5.5 Paired pilot chỉ phát hiện feasibility/regression, không chứng minh savings hay stability; muốn đổi default dựa trên hiệu quả phải có repeated comparable runs được duyệt tiếp.

Gate: chỉ promote candidate khi đủ evidence theo claim; nếu chưa đủ, giữ default và công bố gap.

## Giới hạn thực nghiệm và reporting

Phase 1–2 không cần live model runs. Phase 3 đề xuất tối đa hai probe; Phase 4 bốn run, một/scenario; mỗi run tối đa 600 giây gồm descendants, không tự retry khi timeout. Tổng vòng dispatch/behavior tối đa sáu run, 60 phút run time, không phải ước lượng thời gian triển khai hay credit cap. Chốt model/effort/runtime khả dụng trước chạy và giữ cố định giữa behavioral runs; named-role pins phải được khai báo, không claim toàn bộ agent dùng cùng model.

Đây là giới hạn đề xuất cho bước triển khai sau, không phải authorization chạy ngay từ yêu cầu lập plan. Resource pilot Phase 5 cần quyết định riêng về số run/usage budget. Nếu muốn hard credit cap nhưng runtime không có task-attributed counter/enforcement, báo chưa bảo đảm; time cap không thay credit cap. Chụp usage baseline/final khi công cụ cung cấp, không polling tốn kém.

Raw runs/builds trong ignored dist/. Reviewed summaries trong docs/validation/, không publish raw secrets/chat/source. Graph record theo milestones, survey quan sát before/during/after riêng và chỉ đề xuất retro; không tự sửa environment từ findings.

## Verification chung và hoàn tất

Sau mỗi phase có distributed edits: refresh manifest bằng python scripts/build_release.py; python scripts/validate_package.py; python -m unittest discover -s tests -v. Focused tests trước để phát hiện lỗi sớm; không chạy lại live scenarios chỉ vì package manifest đổi. Nếu thay installer/package behavior, thêm extracted-ZIP lifecycle check; policy-only changes cần validate installed self-contained skills, không mặc định chạy lại toàn bộ recovery workflow.

Shared integration write scope: release-manifest.json và docs/validation/ tương ứng; VERSION/README chỉ khi cần mô tả thay đổi hành vi/release, không bump version tự động trong plan. Theo distribution.json hiện có, plan ở docs/plans/ được đóng gói như tài liệu; nó không phải instruction được tự động nạp để thực thi skill.

Mỗi phase report: changed files, criterion results, commands, trace pointers, limits và next gate. Hoàn tất không yêu cầu git commit/push, deploy hay sửa global settings. Đầu ra cuối là policy/contract nhất quán, runtime evidence có phạm vi rõ và kết luận resource economy trung thực, không chỉ một graph đẹp.
