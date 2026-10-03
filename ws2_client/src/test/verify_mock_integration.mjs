/**
 * Verification script connecting to the live mock server (ws4_eval/mock_server.py).
 * Runs directly in Node (node verify_mock_integration.mjs).
 */

const AUDIO_MAGIC_0 = 0xAA;
const AUDIO_MAGIC_1 = 0xBB;
const AUDIO_HEADER_SIZE = 16;

function hashParticipantId(id) {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = ((hash << 5) - hash + id.charCodeAt(i)) | 0;
  }
  return Math.abs(hash) & 0xffff;
}

function buildAudioHeader(participantIdHash, seqNum, captureTs) {
  const buf = new ArrayBuffer(AUDIO_HEADER_SIZE);
  const view = new DataView(buf);
  view.setUint8(0, AUDIO_MAGIC_0);
  view.setUint8(1, AUDIO_MAGIC_1);
  view.setUint16(2, participantIdHash, false);
  view.setUint32(4, seqNum, false);
  view.setBigUint64(8, captureTs, false);
  return buf;
}

async function runVerification() {
  console.log("Connecting to ws://localhost:8000...");
  const ws = new WebSocket("ws://localhost:8000");
  ws.binaryType = "arraybuffer";

  await new Promise((resolve, reject) => {
    ws.onopen = () => {
      console.log("✓ Connected to Mock Server");
      resolve();
    };
    ws.onerror = (e) => reject(new Error("Connection failed: " + e.message));
  });

  // 1. Send JOIN
  console.log("Sending JOIN request...");
  const joinMsg = {
    type: "JOIN",
    session_id: "ROOM_VERIFY",
    participant_name: "Alice",
  };
  ws.send(JSON.stringify(joinMsg));

  // 2. Receive JOIN_ACK
  const ack = await new Promise((resolve) => {
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "JOIN_ACK") {
        resolve(data);
      }
    };
  });
  console.log(`✓ Received JOIN_ACK: participant_id=${ack.participant_id}`);

  // 3. Send 100ms 16kHz audio frame
  console.log("Building and sending 100ms 16kHz audio frame with 16-byte header...");
  const pidHash = hashParticipantId(ack.participant_id);
  const headerBuf = buildAudioHeader(pidHash, 1, BigInt(Date.now()));
  const samples = new Float32Array(1600); // 1600 samples = 100ms at 16kHz
  for (let i = 0; i < 1600; i++) {
    samples[i] = Math.sin((2 * Math.PI * 440 * i) / 16000) * 0.3;
  }

  const frame = new Uint8Array(AUDIO_HEADER_SIZE + samples.byteLength);
  frame.set(new Uint8Array(headerBuf), 0);
  frame.set(new Uint8Array(samples.buffer), AUDIO_HEADER_SIZE);

  // Set up caption listener
  const captionPromise = new Promise((resolve) => {
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "CAPTION") {
        resolve(data);
      }
    };
  });

  ws.send(frame);
  console.log("Audio frame sent (6416 bytes). Waiting for CaptionEvent...");

  const caption = await captionPromise;
  console.log("✓ Received CaptionEvent from Mock Server:");
  console.log(JSON.stringify(caption, null, 2));

  if (caption.speaker_id === ack.participant_id && caption.text) {
    console.log("\n==========================================");
    console.log(">>> SUCCESS: Mock Server Integration Verified! <<<");
    console.log("==========================================");
  } else {
    throw new Error("CaptionEvent did not match expected structure");
  }

  ws.close();
  process.exit(0);
}

runVerification().catch((err) => {
  console.error("Verification failed:", err);
  process.exit(1);
});
