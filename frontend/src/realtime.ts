export type DemoStatus =
	| "provisioning"
	| "onboarding"
	| "preparing"
	| "ready"
	| "failed";

export type VoiceActivity = "idle" | "listening" | "speaking";

export type AssistantCaptionEvent =
	| {
			type: "started" | "updated";
			responseId?: string;
			transcript: string;
	  }
	| {
			type: "stopped" | "cleared";
			responseId?: string;
	  };

export type DemoSession = {
	id: string;
	status: DemoStatus;
	expires_at: string;
	view_url?: string;
	error?: string;
};

type RealtimeEvent = {
	type?: string;
	delta?: string;
	transcript?: string;
	item_id?: string;
	response_id?: string;
	name?: string;
	item?: {
		type?: string;
		output?: string;
	};
	error?: {
		message?: string;
	};
};

type VoiceAnswer = {
	sdp: string;
	call_id: string;
};

type DemoCallbacks = {
	onSession: (session: DemoSession) => void;
	onAssistantTranscript: (text: string) => void;
	onAssistantCaptionEvent: (event: AssistantCaptionEvent) => void;
	onUserTranscript: (text: string) => void;
	onVoiceActivity: (activity: VoiceActivity) => void;
	onMeetingCard: () => void;
	onError: (message: string) => void;
};

export type DemoConnection = {
	close: () => Promise<void>;
};

const ACTIVE_DEMO_SESSION_KEY = "walt-active-demo-session";

export async function connectDemo(
	callbacks: DemoCallbacks,
): Promise<DemoConnection> {
	await deletePreviousDemoSession();
	const created = await requestJson<DemoSession>("/api/demo-sessions", {
		method: "POST",
	});
	setActiveDemoSession(created.id);
	callbacks.onSession(created);

	const peer = new RTCPeerConnection();
	let microphone: MediaStream | undefined;
	let closed = false;
	let poll: number | undefined;
	window.addEventListener("pagehide", handlePageHide);

	function handlePageHide() {
		if (closed) {
			return;
		}

		closed = true;
		stopLocalConnection();
		void deleteDemoSession(created.id, true);
	}

	async function close() {
		if (closed) {
			return;
		}

		closed = true;
		window.removeEventListener("pagehide", handlePageHide);
		stopLocalConnection();
		await deleteDemoSession(created.id, true).catch(() => undefined);
		clearActiveDemoSession(created.id);
	}

	function stopLocalConnection() {
		if (poll !== undefined) {
			window.clearInterval(poll);
		}
		for (const track of microphone?.getTracks() ?? []) {
			track.stop();
		}
		peer.close();
	}

	try {
		microphone = await navigator.mediaDevices.getUserMedia({
			audio: {
				autoGainControl: true,
				echoCancellation: true,
				noiseSuppression: true,
			},
		});
		for (const track of microphone.getTracks()) {
			peer.addTrack(track, microphone);
		}

		const remoteAudio = new Audio();
		remoteAudio.autoplay = true;
		peer.ontrack = (event) => {
			remoteAudio.srcObject = event.streams[0];
		};

		const events = peer.createDataChannel("oai-events");
		let assistantTranscript = "";
		let assistantTranscriptItemId: string | undefined;
		let assistantTranscriptResponseId: string | undefined;
		let captionPlaybackActive = false;

		function updateAssistantCaption() {
			if (!captionPlaybackActive) {
				return;
			}

			callbacks.onAssistantCaptionEvent({
				type: "updated",
				responseId: assistantTranscriptResponseId,
				transcript: assistantTranscript,
			});
		}

		function startAssistantCaption(responseId?: string) {
			if (responseId && assistantTranscriptResponseId !== responseId) {
				assistantTranscript = "";
				assistantTranscriptItemId = undefined;
			}
			assistantTranscriptResponseId = responseId;
			captionPlaybackActive = true;
			callbacks.onAssistantCaptionEvent({
				type: "started",
				responseId: assistantTranscriptResponseId,
				transcript: assistantTranscript,
			});
			callbacks.onVoiceActivity("speaking");
		}

		function stopAssistantCaption(responseId?: string) {
			if (responseId) {
				assistantTranscriptResponseId = responseId;
			}
			updateAssistantCaption();
			if (captionPlaybackActive) {
				callbacks.onAssistantCaptionEvent({
					type: "stopped",
					responseId: assistantTranscriptResponseId,
				});
			}
			captionPlaybackActive = false;
			callbacks.onVoiceActivity("listening");
		}

		function clearAssistantCaption(responseId?: string) {
			callbacks.onAssistantCaptionEvent({
				type: "cleared",
				responseId: responseId ?? assistantTranscriptResponseId,
			});
			captionPlaybackActive = false;
			callbacks.onVoiceActivity("listening");
		}

		events.addEventListener("message", (message) => {
			let event: RealtimeEvent;
			try {
				event = JSON.parse(message.data) as RealtimeEvent;
			} catch {
				return;
			}

			if (
				event.type === "response.output_audio_transcript.delta" &&
				event.delta &&
				event.item_id
			) {
				if (assistantTranscriptItemId !== event.item_id) {
					assistantTranscript = "";
					assistantTranscriptItemId = event.item_id;
				}
				assistantTranscriptResponseId = event.response_id;
				assistantTranscript += event.delta;
				callbacks.onAssistantTranscript(assistantTranscript);
				updateAssistantCaption();
				return;
			}

			if (
				event.type === "response.output_audio_transcript.done" &&
				event.transcript &&
				event.item_id
			) {
				assistantTranscriptItemId = event.item_id;
				assistantTranscriptResponseId = event.response_id;
				assistantTranscript = event.transcript;
				callbacks.onAssistantTranscript(assistantTranscript);
				updateAssistantCaption();
				return;
			}

			if (event.type === "output_audio_buffer.started") {
				startAssistantCaption(event.response_id);
				return;
			}

			if (event.type === "output_audio_buffer.stopped") {
				stopAssistantCaption(event.response_id);
				return;
			}

			if (event.type === "output_audio_buffer.cleared") {
				clearAssistantCaption(event.response_id);
				return;
			}

			if (
				(event.type === "response.function_call_arguments.done" &&
					event.name === "show_meeting_card") ||
				isMeetingCardOutput(event)
			) {
				callbacks.onMeetingCard();
				return;
			}

			if (event.type === "input_audio_buffer.speech_started") {
				clearAssistantCaption();
				callbacks.onUserTranscript("");
				return;
			}

			if (
				event.type ===
					"conversation.item.input_audio_transcription.completed" &&
				event.transcript
			) {
				callbacks.onUserTranscript(event.transcript);
				return;
			}

			if (event.type === "error") {
				callbacks.onError(
					event.error?.message ?? "The voice connection encountered an error.",
				);
				void close();
			}
		});

		const offer = await peer.createOffer();
		await peer.setLocalDescription(offer);
		const response = await fetch(`/api/demo-sessions/${created.id}/offer`, {
			method: "POST",
			headers: { "Content-Type": "application/sdp" },
			body: offer.sdp,
		});
		if (!response.ok) {
			const payload = (await response.json().catch(() => null)) as {
				detail?: string;
			} | null;
			throw new Error(
				payload?.detail ?? "The voice connection could not be started.",
			);
		}
		const answer = (await response.json()) as VoiceAnswer;
		await peer.setRemoteDescription({ type: "answer", sdp: answer.sdp });
		await waitForChannel(events);
		callbacks.onVoiceActivity("listening");
		events.send(JSON.stringify({ type: "response.create" }));

		let polling = false;
		poll = window.setInterval(async () => {
			if (closed || polling) {
				return;
			}
			polling = true;
			try {
				const session = await requestJson<DemoSession>(
					`/api/demo-sessions/${created.id}`,
				);
				callbacks.onSession(session);
				if (session.status === "failed") {
					callbacks.onError(session.error ?? "The demo could not be started.");
					await close();
				} else if (session.status === "ready" && poll !== undefined) {
					window.clearInterval(poll);
				}
			} catch (pollingError) {
				callbacks.onError(errorMessage(pollingError));
				await close();
			} finally {
				polling = false;
			}
		}, 1000);

		return { close };
	} catch (error) {
		await close();
		throw error;
	}
}

function isMeetingCardOutput(event: RealtimeEvent) {
	if (
		event.type !== "conversation.item.created" ||
		event.item?.type !== "function_call_output" ||
		!event.item.output
	) {
		return false;
	}

	try {
		return containsMeetingCardSignal(JSON.parse(event.item.output));
	} catch {
		return false;
	}
}

function containsMeetingCardSignal(value: unknown): boolean {
	if (Array.isArray(value)) {
		return value.some(containsMeetingCardSignal);
	}
	if (!value || typeof value !== "object") {
		return false;
	}

	const record = value as Record<string, unknown>;
	if (record.event === "show_meeting_card" && record.visible === true) {
		return true;
	}
	return Object.values(record).some(containsMeetingCardSignal);
}

async function deletePreviousDemoSession() {
	const sessionId = activeDemoSession();
	if (!sessionId) {
		return;
	}

	await deleteDemoSession(sessionId);
	clearActiveDemoSession(sessionId);
}

async function deleteDemoSession(sessionId: string, keepalive = false) {
	const response = await fetch(`/api/demo-sessions/${sessionId}`, {
		method: "DELETE",
		keepalive,
	});
	if (!response.ok) {
		throw new Error("The previous demo session could not be cleaned up.");
	}
}

function activeDemoSession() {
	try {
		return window.sessionStorage.getItem(ACTIVE_DEMO_SESSION_KEY);
	} catch {
		return null;
	}
}

function setActiveDemoSession(sessionId: string) {
	try {
		window.sessionStorage.setItem(ACTIVE_DEMO_SESSION_KEY, sessionId);
	} catch {
		return;
	}
}

function clearActiveDemoSession(sessionId: string) {
	try {
		if (activeDemoSession() === sessionId) {
			window.sessionStorage.removeItem(ACTIVE_DEMO_SESSION_KEY);
		}
	} catch {
		return;
	}
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
	const response = await fetch(url, init);
	if (!response.ok) {
		const payload = (await response.json().catch(() => null)) as {
			detail?: string;
		} | null;
		throw new Error(payload?.detail ?? "The demo request failed.");
	}
	return (await response.json()) as T;
}

function waitForChannel(channel: RTCDataChannel): Promise<void> {
	if (channel.readyState === "open") {
		return Promise.resolve();
	}
	return new Promise((resolve, reject) => {
		channel.addEventListener("open", () => resolve(), { once: true });
		channel.addEventListener(
			"error",
			() => reject(new Error("The voice event channel failed.")),
			{ once: true },
		);
	});
}

function errorMessage(error: unknown) {
	return error instanceof Error
		? error.message
		: "The demo encountered an error.";
}
