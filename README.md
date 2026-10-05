# Homework 2: Protect Agent Messages

Run all commands inside the course VM, using NAT networking.
This project uses local simulations and does not execute tool commands.

## Environment setup

From the directory containing hw2:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install cryptography==49.0.0 pytest==9.1.1
cd hw2
```

On Ubuntu, if virtual environment creation fails because ensurepip
is missing, install python3.12-venv first.

## DH parameters

The submission includes ffdhe3072.pem. If it needs to be regenerated:

```bash
openssl genpkey -genparam -algorithm DH -pkeyopt group:ffdhe3072 -out ffdhe3072.pem
```

Requires OpenSSL 3.0 or newer.

## Run demonstrations and tests

```bash
python baseline_ctr.py
python handshake.py
python -m pytest -v tests
```

baseline_ctr.py demonstrates unauthenticated CTR modification and replay.
handshake.py demonstrates authenticated DH and fresh session keys.
secure_record.py provides seal(), open_record(), and make_states().
The tests exercise bidirectional records and rejection of attacks.

## Evidence

- lab_preparation.txt: Python, OpenSSL, and package versions
- task1_results.txt: CTR modification and replay demonstration
- task2_results.txt: authenticated handshake demonstration
- task3_results.txt: bidirectional records and replay rejection
- task4_results.txt: automated test results

## Scope and limitations

RSA identity keys are generated in memory and reused across the two
sessions in the handshake demonstration. Trusted public-key bindings
are provisioned directly in the simulation, not learned from the peer.
A new process creates new identity keys.

Each endpoint must retain its sending and receiving states for the
session. Resetting sequence numbers with the same keys is unsafe.
The simulation is single-threaded and has no persistent session storage.

The record format follows the assignment exactly. With standard CTR,
a record longer than 16 bytes consumes multiple counter blocks.
Its later counter blocks can overlap those of subsequent records
because the starting IV increases by only one per record.
The demonstrations and valid-record tests use messages of at most
16 bytes. General multi-block traffic requires a revised counter
allocation scheme approved by the instructor.

Cryptographic authentication does not authorize a tool call or make
an endpoint trustworthy.
