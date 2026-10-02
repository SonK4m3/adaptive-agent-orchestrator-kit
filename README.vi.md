# Adaptive Agent Orchestrator cho Codex

Bộ skill Codex có thể cài đặt, dành cho công việc phần mềm: chọn topology subagent nhỏ nhất nhưng hữu ích, giữ acceptance criteria, thích ứng khi phát hiện mới làm thay đổi kế hoạch và kiểm chứng kết quả tích hợp.

**Ưu tiên:** làm đúng, đủ yêu cầu → deadline/thời gian → token và chi phí.

## Thành phần

- Hai entrypoint skill tương đương, tự chứa: `adaptive-agent-orchestrator` và `astra-orchestrator` (cài một hoặc cả hai).
- 10 sơ đồ Mermaid cho routing, root-only, focused, collaborative, full orchestration, debug, deadline, tiết kiệm, đổi scope và Jev-assisted.
- 8 role có namespace trong `profiles/adaptive/codex/agents/`; skill vẫn dùng được nếu không cài role.
- Hai profile tài nguyên: `adaptive` (capacity 4) và `adaptive-max-2-subagents` (capacity 2); dùng chung skill và model bindings hiện tại. Profile không ép topology.
- Template task/delegation/run record, hướng dẫn model/evidence, protocol đánh giá và coding fixture.
- [Graph snapshot](skills/adaptive-agent-orchestrator/assets/graph-record.md) theo workstream, kiểm tra ownership/handoff và harness khảo sát riêng biệt; [gate runtime và coverage](docs/validation/AGENT-GRAPH-IMPLEMENTATION-2026-10-01.md) được ghi rõ, chưa coi là multi-agent pass.
- Installer Python chuẩn, manifest toàn vẹn, lệnh doctor, backup có thể khôi phục và checksum ZIP.

Diagram chỉ mô tả pattern, không phải workflow engine thực thi được. Hành vi Codex đến từ `SKILL.md` và khả năng subagent của runtime. Jev chỉ là hướng tích hợp tùy chọn được mô tả; gói này không cài hay chạy Jev.

## Cài đặt

### Setup project-local bằng AI

Khi skill đã được publish lên repository:

```sh
npx skills add https://github.com/SonK4m3/adaptive-agent-orchestrator-kit --skill adaptive-orchestrator-setup
```

Hoặc gửi Codex toàn bộ [skill setup](skills/adaptive-orchestrator-setup/SKILL.md), kèm đường dẫn project đích. Skill bắt đầu bằng preview chỉ đọc và chờ duyệt trước khi ghi: cài skill vào `.agents/skills/`, role tùy chọn vào `.codex/agents/`, thêm routing ở cuối `AGENTS.md` và giữ nội dung cũ. Cap profile chỉ được merge vào `.codex/config.toml` khi đã duyệt; không sửa global config, root model/effort, approvals hay credentials. Khuyến nghị pilot `adaptive-max-2-subagents`, không ép số agent. JEV mặc định không bật và không phải điều kiện để dùng L0–L3. Lệnh cài remote chưa được chạy kiểm chứng trong thay đổi này.

Sau setup, mở chat Codex mới tại project và dùng `$adaptive-agent-orchestrator` hoặc `$astra-orchestrator`. Kiểm tra file không thay thế bằng chứng runtime discovery/dispatch.

### Installer Codex-home hiện có

Setup tự check stable release khi bắt đầu, báo link release notes và hỏi riêng trước khi tải/chạy (mặc định No). Check lỗi thì cảnh báo và tiếp tục bản local; bỏ qua bằng `.\setup.ps1 -Offline` hoặc `sh ./setup.sh --offline`. Check/update chủ động: `.\update.ps1 -CheckOnly`, `.\update.ps1`, hoặc `sh ./update.sh --check`, `sh ./update.sh`. Lệnh chủ động lỗi trả exit code khác 0. Đây là so sánh VERSION của bộ source, không phải phiên bản đã cài ở từng project.

Skill setup dùng `python scripts/update.py --check --json`, rồi `--stage-dir PATH_MOI` nếu user duyệt tải: không chạy installer Codex-home, mà preview lại setup project-local. Xem [cơ chế update và giới hạn](guides/UPDATES.md). Chưa có background service hay thay đổi global config.

Cần Python 3.11 trở lên, không cần package bên thứ ba. Giải nén ZIP và chạy setup tương tác:

```sh
# macOS/Linux
./setup.sh
```

```powershell
# Windows PowerShell
.\setup.ps1
```

Setup hỏi profile, skill entrypoint, 8 role tùy chọn, có cài preset runtime vào file riêng hay không (mặc định không), Codex home đích và thư mục project cần đăng ký skill. Sau khi cài thành công, setup tự thêm block chỉ dẫn vào cuối `AGENTS.md` của project đã chọn; giữ nguyên nội dung cũ, không thêm trùng khi chạy lại. Enter tại bước chọn project để bỏ qua. Mặc định Codex home dùng `$CODEX_HOME` hoặc `~/.codex`. Muốn cài không tương tác thì dùng installer trực tiếp:

```sh
python3 scripts/manage.py install
python3 scripts/manage.py doctor
python3 scripts/register_project.py --project /path/to/project --skill both
```

Mặc định cài vào `$CODEX_HOME` hoặc `~/.codex`. Dùng `--target PATH` để chọn Codex home khác. Chỉ cài một skill bằng `--skill astra-orchestrator` hoặc `--skill adaptive-agent-orchestrator`. Chỉ cài skill không cài role bằng `--parts skills`; chỉ cài role bằng `--parts roles`.

Installer không sửa `config.toml`. Nếu đích đã có nội dung khác, installer dừng an toàn; chỉ thay khi truyền `--replace`, và bản cũ được giữ backup trong `.adaptive-agent-orchestrator-backups/`. Mở phiên Codex mới sau khi cài để runtime nhận skill/role.

Muốn bật preset capacity 2 trong phiên CLI mới:

```sh
python3 scripts/manage.py install --profile adaptive-max-2-subagents --with-profile-config
codex -p adaptive-max-2-subagents
```

Preset cài vào `<CODEX_HOME>/adaptive-max-2-subagents.config.toml`, giữ nguyên root model và approvals. Profile chỉ giới hạn tài nguyên; task quyết định chọn L0/L1/L2/L3. Runtime/account vẫn cần xác nhận hỗ trợ cấu hình và model.

Repo tổ chức theo `profiles/`, `guides/`, `scripts/`, `tests/` như upstream; `skills/` giữ hai entrypoint tự chứa dùng chung giữa các profile, `eval/` chứa scenarios/rubrics/fixtures/oracles và `docs/validation/` lưu báo cáo đã review. Xem [đối chiếu upstream](guides/UPSTREAM-COMPARISON.md), [profile](guides/PROFILES.md) và [migration](guides/MIGRATION.md).

```sh
python3 scripts/manage.py uninstall  # backup rồi chỉ gỡ thành phần có receipt
python3 scripts/manage.py restore BACKUP_ID # khôi phục backup, đồng thời giữ bản hiện tại
python3 scripts/manage.py doctor     # kiểm tra integrity gói và hash phần đã cài
```

Nếu nội dung đã cài bị sửa, uninstall sẽ từ chối trừ khi dùng `--force`; kể cả vậy vẫn tạo backup trước. Có thể khôi phục bằng backup ID mà lệnh in ra. File không liên quan và cấu hình Codex được giữ nguyên. `doctor` chỉ kiểm tra file offline, không chứng minh runtime đã nạp skill/model.

## Sử dụng và kiểm thử

Skill độc lập `task-retro-survey` nằm trong `.agents/skills/task-retro-survey/` của source checkout để team khảo sát trước/trong/sau task và làm retro. Copy cả folder cho đồng nghiệp; log lưu trong `runs/` được ignore, findings chỉ là đề xuất. Xem [hướng dẫn sử dụng/chia sẻ](guides/TASK-RETRO-SURVEY.md). Skill này được phân phối riêng, không cài qua installer orchestrator.

Đánh giá topology/contract theo [scenario và rubric](eval/scenarios/orchestration.md). Chạy `python scripts/run_orchestration.py --model MODEL --effort EFFORT` để thu trace bốn scenario, tối đa 600 giây mỗi run. Runner thực thi shell không sandbox/không hỏi approval trong scratch workspace; chỉ chạy khi đã cho phép phạm vi này. Log nằm trong `dist/` được ignore. Check hành vi/scope được tự động hóa; dispatch, contract, adaptation và tính chính xác của báo cáo cần đọc trace. Một run mỗi scenario chưa đủ kết luận độ ổn định.

Gọi `$astra-orchestrator` hoặc `$adaptive-agent-orchestrator` trong task lập trình. Cung cấp spec và deadline/ngân sách thực tế nếu có. Skill đánh giá complexity riêng với independence, chọn topology, lưu bằng chứng nghiệm thu và chỉ mở rộng khi phát hiện mới có lý do.

```sh
python3 scripts/validate_package.py
python3 -m unittest discover -s tests -v
```

Muốn thử fixture: copy `eval/fixtures/independent` ra scratch project, yêu cầu Codex implement `TASK.md` bằng skill, sau đó đặt `ORCHESTRATOR_FIXTURE` tới bản copy và chạy `node --test eval/oracles/independent.test.mjs`.

Xem [hướng dẫn tiếng Anh](README.md), [kết quả và giới hạn xác minh](VALIDATION.md), [scenario](eval/scenarios/catalog.md), [ghi nhận nguồn](ATTRIBUTION.md) và [hướng dẫn phát hành](guides/RELEASING.md).

Gói chưa có benchmark so sánh đủ điều kiện chất lượng; không khẳng định tiết kiệm token/thời gian hay tốt nhất cho mọi task. GitHub Actions được cấu hình để test Windows/macOS/Linux, nhưng trạng thái xanh chỉ được khẳng định sau khi workflow chạy thật.
