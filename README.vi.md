# Adaptive Agent Orchestrator cho Codex

Bộ skill Codex có thể cài đặt, dành cho công việc phần mềm: chọn topology subagent nhỏ nhất nhưng hữu ích, giữ acceptance criteria, thích ứng khi phát hiện mới làm thay đổi kế hoạch và kiểm chứng kết quả tích hợp.

**Ưu tiên:** làm đúng, đủ yêu cầu → deadline/thời gian → token và chi phí.

## Thành phần

- Hai entrypoint skill tương đương, tự chứa: `adaptive-agent-orchestrator` và `astra-orchestrator` (cài một hoặc cả hai).
- 10 sơ đồ Mermaid cho routing, root-only, focused, collaborative, full orchestration, debug, deadline, tiết kiệm, đổi scope và Jev-assisted.
- 8 định nghĩa role tùy chọn có namespace trong `roles/`; skill vẫn dùng được nếu không cài role.
- Template task/delegation/run record, hướng dẫn model/evidence, protocol đánh giá và coding fixture.
- Installer Python chuẩn, manifest toàn vẹn, lệnh doctor, backup có thể khôi phục và checksum ZIP.

Diagram chỉ mô tả pattern, không phải workflow engine thực thi được. Hành vi Codex đến từ `SKILL.md` và khả năng subagent của runtime. Jev chỉ là hướng tích hợp tùy chọn được mô tả; gói này không cài hay chạy Jev.

## Cài đặt

Cần Python 3.11 trở lên, không cần package bên thứ ba. Giải nén ZIP và chạy setup tương tác:

```sh
# macOS/Linux
./setup.sh
```

```powershell
# Windows PowerShell
.\setup.ps1
```

Setup hỏi skill entrypoint, có cài 8 role agent hay không, và Codex home đích. Mặc định dùng `$CODEX_HOME` hoặc `~/.codex`. Muốn cài không tương tác thì dùng installer trực tiếp:

```sh
python3 scripts/manage.py install
python3 scripts/manage.py doctor
```

Mặc định cài vào `$CODEX_HOME` hoặc `~/.codex`. Dùng `--target PATH` để chọn Codex home khác. Chỉ cài một skill bằng `--skill astra-orchestrator` hoặc `--skill adaptive-agent-orchestrator`. Chỉ cài skill không cài role bằng `--parts skills`; chỉ cài role bằng `--parts roles`.

Installer không sửa `config.toml`. Nếu đích đã có nội dung khác, installer dừng an toàn; chỉ thay khi truyền `--replace`, và bản cũ được giữ backup trong `.adaptive-agent-orchestrator-backups/`. Mở phiên Codex mới sau khi cài để runtime nhận skill/role.

```sh
python3 scripts/manage.py uninstall  # backup rồi chỉ gỡ thành phần có receipt
python3 scripts/manage.py restore BACKUP_ID # khôi phục backup, đồng thời giữ bản hiện tại
python3 scripts/manage.py doctor     # kiểm tra integrity gói và hash phần đã cài
```

Nếu nội dung đã cài bị sửa, uninstall sẽ từ chối trừ khi dùng `--force`; kể cả vậy vẫn tạo backup trước. Có thể khôi phục bằng backup ID mà lệnh in ra. File không liên quan và cấu hình Codex được giữ nguyên. `doctor` chỉ kiểm tra file offline, không chứng minh runtime đã nạp skill/model.

## Sử dụng và kiểm thử

Gọi `$astra-orchestrator` hoặc `$adaptive-agent-orchestrator` trong task lập trình. Cung cấp spec và deadline/ngân sách thực tế nếu có. Skill đánh giá complexity riêng với independence, chọn topology, lưu bằng chứng nghiệm thu và chỉ mở rộng khi phát hiện mới có lý do.

```sh
python3 eval/validate-kit.py
python3 -m unittest discover -s tests -v
```

Muốn thử fixture: copy `eval/fixture` ra scratch project, yêu cầu Codex implement `TASK.md` bằng skill, sau đó đặt `ORCHESTRATOR_FIXTURE` tới bản copy và chạy `node --test eval/acceptance.test.mjs`.

Xem [hướng dẫn tiếng Anh](README.md), [kết quả và giới hạn xác minh](VALIDATION.md), [scenario](test-scenarios.md), [ghi nhận nguồn](ATTRIBUTION.md) và [hướng dẫn phát hành](docs/RELEASING.md).

Gói chưa có benchmark so sánh đủ điều kiện chất lượng; không khẳng định tiết kiệm token/thời gian hay tốt nhất cho mọi task. GitHub Actions được cấu hình để test Windows/macOS/Linux, nhưng trạng thái xanh chỉ được khẳng định sau khi workflow chạy thật.
