# AI Usage

Tool/model and date:
ChatGPT (Codex; exact model not recorded), October 4, 2026.

Purpose:
Step-by-step terminal guidance, environment troubleshooting,
Python implementation assistance, automated test creation,
and submission documentation.

AI Conversation Log files:
ai_conversation.txt — must be added before submission with the
relevant prompts and responses, including code and corrections.

What I used:
AI-provided commands and code for baseline_ctr.py, handshake.py,
secure_record.py, and the automated tests. AI also helped prepare
README.md and this AI-use record.

What I changed:
During the guided session, I installed the missing Python venv
package and removed an accidentally duplicated block in handshake.py.
The implementation otherwise follows the AI-provided code.
Any additional changes made after this entry should be recorded here.

How I tested it:
I ran Python syntax checks, the CTR modification/replay demonstration,
the authenticated handshake demonstration, and a bidirectional record
and replay check. I ran the automated suite, which reported 20 passing
tests. These tests were AI-assisted; passing them does not constitute
independent verification of the entire design.

One error, limitation, or rejected suggestion:
The prescribed CTR IV layout can overlap counter blocks across
consecutive records when plaintext exceeds 16 bytes. The current
implementation does not prevent this; the limitation is documented
in README.md. The passing short-message tests do not prove security
for multi-block messages.
