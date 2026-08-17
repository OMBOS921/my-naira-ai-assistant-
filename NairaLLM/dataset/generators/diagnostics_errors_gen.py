"""
Diagnostics, Error Messages, & Log Tracebacks Domain Generator for Dataset A.
Generates comprehensive real-world compiler diagnostics, runtime tracebacks, SQL errors, and structured logs.
"""

from __future__ import annotations

from typing import Any


def get_diagnostics_errors_samples() -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []

    def add(sample_id: str, text: str, notes: str = "") -> None:
        samples.append({
            "id": sample_id,
            "domain": "error_messages_diagnostics",
            "language": "en",
            "text": text.strip(),
            "provenance": {
                "provenance_id": f"prov_{sample_id}",
                "author": "nairallm_semantic_curator",
                "license": "Apache-2.0",
                "acquisition_method": "controlled_synthetic",
                "notes": notes or "Realistic error messages, tracebacks, and diagnostic log formats",
            },
        })

    add(
        "sem_err_001",
        """Traceback (most recent call last):
  File "/app/backend/runtime/dispatcher.py", line 184, in dispatch_event
    await handler.execute(event_payload)
  File "/app/backend/modules/memory/vector_store.py", line 92, in execute
    embeddings = self.embedder.generate(event_payload["context_text"])
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/backend/models/embedder.py", line 45, in generate
    tensor_input = torch.tensor(tokens, dtype=torch.long, device=self.device)
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
RuntimeError: CUDA out of memory. Tried to allocate 512.00 MiB (GPU 0; 15.78 GiB total capacity; 14.82 GiB already allocated; 312.00 MiB free; 15.10 GiB reserved in total by PyTorch)
If reserved memory is >> allocated memory try setting max_split_size_mb to avoid fragmentation.""",
        "Python PyTorch CUDA out-of-memory traceback",
    )

    add(
        "sem_err_002",
        """error[E0382]: borrow of moved value: `user_session`
  --> src/auth/session_manager.rs:42:18
   |
38 |     let user_session = create_session(user_id)?;
   |         ------------ move occurs because `user_session` has type `Session`, which does not implement the `Copy` trait
39 |     persist_to_cache(user_session);
   |                      ------------ value moved here
...
42 |     let token = &user_session.token;
   |                  ^^^^^^^^^^^^ value borrowed here after move
   |
help: consider borrowing `user_session` rather than transferring ownership
   |
39 |     persist_to_cache(&user_session);
   |                      +""",
        "Rust borrow checker move semantics compiler error E0382",
    )

    add(
        "sem_err_003",
        """src/network/socket_server.cpp: In member function 'void SocketServer::handle_client(int)':
src/network/socket_server.cpp:158:24: error: no matching function for call to 'bind(int&, sockaddr_in*, long unsigned int)'
  158 |     if (bind(sockfd, &server_addr, sizeof(server_addr)) < 0) {
      |         ~~~~^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
In file included from /usr/include/x86_64-linux-gnu/sys/socket.h:33:
/usr/include/x86_64-linux-gnu/bits/socket.h:120:12: note: candidate: 'int bind(int, const sockaddr*, socklen_t)'
  120 | extern int bind (int __fd, const struct sockaddr *__addr, socklen_t __len) __THROW;
      |            ^~~~
/usr/include/x86_64-linux-gnu/bits/socket.h:120:51: note:   no known conversion for argument 2 from 'sockaddr_in*' to 'const sockaddr*'
  120 | extern int bind (int __fd, const struct sockaddr *__addr, socklen_t __len) __THROW;
      |                            ~~~~~~~~~~~~~~~~~~~~~~~^~~~~~
help: cast struct pointer using (struct sockaddr*) or reinterpret_cast<const sockaddr*>(&server_addr)""",
        "C++ GCC socket bind type mismatch compilation diagnostic",
    )

    add(
        "sem_err_004",
        """ERROR:  duplicate key value violates unique constraint "users_email_key"
DETAIL:  Key (email)=(alex.developer@example.com) already exists.
STATEMENT:  INSERT INTO users (id, username, email, created_at) VALUES ('9f8b2c41-71e8-4221-8289-492cb71a3994', 'alex_dev', 'alex.developer@example.com', NOW());
HINT:  Use ON CONFLICT (email) DO UPDATE or check table constraints before inserting.""",
        "PostgreSQL unique constraint violation error with SQL hint",
    )

    add(
        "sem_err_005",
        """2026/08/16 14:40:22 [error] 1482#1482: *89410 upstream timed out (110: Connection timed out) while reading response header from upstream, client: 198.51.100.42, server: api.naira-os.org, request: "POST /v1/chat/completions HTTP/2.0", upstream: "http://127.0.0.1:8000/v1/chat/completions", host: "api.naira-os.org", referrer: "https://app.naira-os.org/"
2026/08/16 14:40:22 [warn] 1482#1482: *89410 a client request body is buffered to a temporary file /var/lib/nginx/body/0000000042, client: 198.51.100.42, server: api.naira-os.org, request: "POST /v1/chat/completions HTTP/2.0" """,
        "Nginx reverse proxy upstream timeout 110 error log",
    )

    return samples
