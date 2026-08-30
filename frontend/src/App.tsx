import {
	ArrowRight,
	ArrowUpRight,
	CalendarDays,
	Clock3,
	RotateCcw,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { DesktopViewer } from "./DesktopViewer";
import {
	connectDemo,
	type DemoConnection,
	type DemoSession,
	type VoiceActivity,
} from "./realtime";

type ExperienceStage =
	| "landing"
	| "connecting"
	| "conversation"
	| "preparing"
	| "handoff"
	| "demo"
	| "meeting"
	| "error";

const HANDOFF_DURATION_MS = 500;

const waltLetters = [
	{ letter: "W", meaning: "walkthrough" },
	{ letter: "A", meaning: "agent" },
	{ letter: "L", meaning: "live" },
	{ letter: "T", meaning: "talkative" },
] as const;

const voiceActivityLabels: Record<VoiceActivity, string> = {
	idle: "Getting ready",
	listening: "Listening",
	speaking: "Walt is speaking",
};

export function App() {
	const demoConnection = useRef<DemoConnection | null>(null);
	const isConnecting = useRef(false);
	const isMeetingEndState = useRef(window.location.hash === "#meeting");
	const [stage, setStage] = useState<ExperienceStage>(initialExperienceStage);
	const [activeLetter, setActiveLetter] = useState<number | null>(null);
	const [assistantTranscript, setAssistantTranscript] = useState("");
	const [assistantCaption, setAssistantCaption] = useState("");
	const [userTranscript, setUserTranscript] = useState("");
	const [voiceActivity, setVoiceActivity] = useState<VoiceActivity>("idle");
	const [viewUrl, setViewUrl] = useState<string | null>(null);
	const [isDesktopLoaded, setIsDesktopLoaded] = useState(false);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		function handleLocationChange() {
			if (isMeetingEndState.current) {
				if (window.location.hash !== "#meeting") {
					window.history.replaceState(null, "", "#meeting");
				}
				setStage("meeting");
				return;
			}

			if (window.location.hash === "#demo") {
				setStage((currentStage) =>
					currentStage === "landing" ? "connecting" : currentStage,
				);
				return;
			}

			void demoConnection.current?.close();
			demoConnection.current = null;
			setStage("landing");
		}

		window.addEventListener("hashchange", handleLocationChange);
		window.addEventListener("popstate", handleLocationChange);
		return () => {
			window.removeEventListener("hashchange", handleLocationChange);
			window.removeEventListener("popstate", handleLocationChange);
		};
	}, []);

	useEffect(() => {
		return () => {
			void demoConnection.current?.close();
		};
	}, []);

	useEffect(() => {
		if (stage !== "handoff" || !isDesktopLoaded) {
			return;
		}

		const timeout = window.setTimeout(
			() => setStage("demo"),
			HANDOFF_DURATION_MS,
		);
		return () => window.clearTimeout(timeout);
	}, [isDesktopLoaded, stage]);

	const handleSessionUpdate = useCallback((session: DemoSession) => {
		if (session.status === "onboarding") {
			setStage("conversation");
		}
		if (session.status === "preparing") {
			setStage("preparing");
		}
		if (session.status === "ready" && session.view_url) {
			setViewUrl(session.view_url);
			setStage("handoff");
		}
	}, []);
	const handleDesktopReady = useCallback(() => setIsDesktopLoaded(true), []);
	const handleMeetingCard = useCallback(() => {
		isMeetingEndState.current = true;
		window.history.replaceState(null, "", "#meeting");
		setStage("meeting");

		const connection = demoConnection.current;
		demoConnection.current = null;
		void connection?.close();
	}, []);

	const startVoiceSession = useCallback(async () => {
		if (isConnecting.current) {
			return;
		}

		isConnecting.current = true;
		setError(null);
		setAssistantTranscript("");
		setAssistantCaption("");
		setUserTranscript("");
		setVoiceActivity("idle");
		setViewUrl(null);
		setIsDesktopLoaded(false);
		setStage("connecting");

		try {
			await demoConnection.current?.close();
			const connection = await connectDemo({
				onSession: handleSessionUpdate,
				onAssistantTranscript: setAssistantTranscript,
				onAssistantCaption: setAssistantCaption,
				onUserTranscript: setUserTranscript,
				onVoiceActivity: setVoiceActivity,
				onMeetingCard: handleMeetingCard,
				onError: (message) => {
					setError(message);
					setStage("error");
				},
			});
			if (window.location.hash !== "#demo") {
				await connection.close();
				return;
			}
			demoConnection.current = connection;
			setStage((currentStage) =>
				currentStage === "connecting" ? "conversation" : currentStage,
			);
		} catch (connectionError) {
			setError(errorMessage(connectionError));
			setStage("error");
		} finally {
			isConnecting.current = false;
		}
	}, [handleMeetingCard, handleSessionUpdate]);

	useEffect(() => {
		if (
			stage === "connecting" &&
			window.location.hash === "#demo" &&
			!demoConnection.current &&
			!isConnecting.current
		) {
			void startVoiceSession();
		}
	}, [stage, startVoiceSession]);

	function openDemo() {
		window.history.pushState(null, "", "#demo");
		void startVoiceSession();
	}

	const isDemo = stage === "demo";
	const isRevealingDesktop = isDemo || (stage === "handoff" && isDesktopLoaded);
	const isVoiceActive =
		stage === "connecting" ||
		stage === "conversation" ||
		stage === "preparing" ||
		stage === "handoff";
	const onboardingTranscript = assistantTranscript || "Walt is getting ready…";

	if (stage === "landing") {
		return (
			<main className="landing">
				<section className="landing-hero">
					<h1 className="walt-lockup" aria-label="WALT">
						{waltLetters.map(({ letter, meaning }, index) => (
							<span
								className="walt-letter-item"
								data-active={activeLetter === index}
								key={letter}
							>
								<button
									aria-label={`${letter} means ${meaning}`}
									aria-pressed={activeLetter === index}
									className="walt-letter"
									onClick={() =>
										setActiveLetter((currentLetter) =>
											currentLetter === index ? null : index,
										)
									}
									type="button"
								>
									<span aria-hidden="true">{letter}</span>
								</button>
								<span className="letter-meaning" aria-hidden="true">
									{meaning}
								</span>
							</span>
						))}
					</h1>
					<button className="demo-button" type="button" onClick={openDemo}>
						<span>meet walt</span>
						<span className="demo-button-arrow" aria-hidden="true">
							<ArrowUpRight strokeWidth={2.25} />
						</span>
					</button>
				</section>

				<section className="pricing" aria-labelledby="pricing-title">
					<header className="pricing-header">
						<p>Pricing</p>
						<h2 id="pricing-title">Free, for now.</h2>
					</header>

					<article className="pricing-card">
						<div className="pricing-plan">
							<p>The only plan</p>
							<h3>$0</h3>
							<span>
								until the remaining credits become zero remaining credits.
							</span>
						</div>

						<ul>
							<li>Everything currently in the demo</li>
							<li>No checkout, invoices, or payment details</li>
							<li>No account to create and therefore none to forget</li>
							<li>
								Availability is directly correlated with our credit balance
							</li>
						</ul>
					</article>

					<p className="pricing-disclaimer">
						If the demo stops, the pricing experiment has concluded.
					</p>
				</section>
			</main>
		);
	}

	if (stage === "meeting") {
		return <MeetingPage />;
	}

	return (
		<main
			className="experience"
			data-desktop-ready={isDesktopLoaded}
			data-stage={stage}
		>
			<div className="desktop">
				<DesktopViewer
					onReady={handleDesktopReady}
					previewUrl={viewUrl ?? undefined}
				/>
			</div>

			<div
				className={`guide-orb ${isRevealingDesktop ? "guide-orb-demo" : "guide-orb-onboarding"}`}
				data-activity={voiceActivity}
				aria-hidden="true"
			/>

			{!isDemo && (
				<section className="onboarding" aria-label="Voice demo onboarding">
					<div className="onboarding-step" key={stage}>
						{stage === "connecting" && <h1>Getting Walt on the line…</h1>}

						{stage === "conversation" && (
							<>
								<h1 className="voice-question" aria-live="polite">
									{onboardingTranscript}
								</h1>
								{userTranscript && (
									<p className="user-transcript">“{userTranscript}”</p>
								)}
							</>
						)}

						{stage === "preparing" && <h1>Got it. Building your demo…</h1>}

						{stage === "handoff" && <h1>Your demo is ready.</h1>}

						{stage === "error" && (
							<div className="onboarding-error">
								<h1>Walt lost the line.</h1>
								<p role="alert">
									{error ?? "The voice session could not be started."}
								</p>
								<button
									className="begin-button"
									type="button"
									onClick={startVoiceSession}
								>
									<RotateCcw aria-hidden="true" />
									Try again
								</button>
							</div>
						)}
					</div>
				</section>
			)}

			{isDemo && (
				<div className="narration" data-activity={voiceActivity}>
					<p aria-live="polite">
						{assistantCaption ||
							(voiceActivity === "speaking"
								? "…"
								: "Walt is ready when you are.")}
					</p>
				</div>
			)}

			<span className="sr-only" aria-live="polite">
				{isVoiceActive ? voiceActivityLabels[voiceActivity] : ""}
			</span>
		</main>
	);
}

function MeetingPage() {
	return (
		<main className="meeting-page">
			<div className="meeting-backdrop" aria-hidden="true" />
			<section className="meeting-card" aria-labelledby="meeting-title">
				<header className="meeting-summary">
					<div className="meeting-mark" aria-hidden="true" />
					<h1 id="meeting-title">Talk to the team.</h1>
					<p className="meeting-description">
						Choose a time that works for you.
					</p>

					<ul className="meeting-details" aria-label="Meeting details">
						<li>
							<Clock3 aria-hidden="true" />
							30 minutes
						</li>
						<li>
							<CalendarDays aria-hidden="true" />
							Video call
						</li>
					</ul>
				</header>

				<form
					className="meeting-form"
					onSubmit={(event) => event.preventDefault()}
				>
					<fieldset>
						<legend>Choose a day</legend>
						<div className="meeting-options meeting-days">
							<MeetingOption name="meeting-day" label="Mon" value="31" />
							<MeetingOption
								name="meeting-day"
								label="Tue"
								value="01"
								defaultChecked
							/>
							<MeetingOption name="meeting-day" label="Wed" value="02" />
						</div>
					</fieldset>

					<fieldset>
						<legend>Choose a time</legend>
						<div className="meeting-options meeting-times">
							<MeetingOption name="meeting-time" value="10:00" />
							<MeetingOption name="meeting-time" value="11:30" defaultChecked />
							<MeetingOption name="meeting-time" value="14:00" />
						</div>
					</fieldset>

					<div className="meeting-fields">
						<label>
							<span>Name</span>
							<input type="text" name="name" placeholder="Your name" />
						</label>
						<label>
							<span>Work email</span>
							<input type="email" name="email" placeholder="you@company.com" />
						</label>
					</div>

					<button className="meeting-submit" type="submit">
						Continue
						<ArrowRight aria-hidden="true" />
					</button>
				</form>
			</section>
		</main>
	);
}

type MeetingOptionProps = {
	defaultChecked?: boolean;
	label?: string;
	name: string;
	value: string;
};

function MeetingOption({
	defaultChecked,
	label,
	name,
	value,
}: MeetingOptionProps) {
	return (
		<label className="meeting-option">
			<input
				defaultChecked={defaultChecked}
				name={name}
				type="radio"
				value={value}
			/>
			<span>
				{label && <small>{label}</small>}
				<strong>{value}</strong>
			</span>
		</label>
	);
}

function errorMessage(error: unknown) {
	if (error instanceof DOMException && error.name === "NotAllowedError") {
		return "Microphone access is off. Allow it in your browser, then try again.";
	}
	return error instanceof Error
		? error.message
		: "The voice session could not be started.";
}

function initialExperienceStage(): ExperienceStage {
	if (window.location.hash === "#meeting") {
		return "meeting";
	}
	if (window.location.hash === "#demo") {
		return "connecting";
	}
	return "landing";
}
