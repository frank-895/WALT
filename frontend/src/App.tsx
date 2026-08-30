export function App() {
	return (
		<main className="demo">
			<div className="desktop" aria-label="Virtual machine screen" role="img" />
			<div className="narration">
				<div className="orb" aria-label="Walt is speaking" role="img" />
				<p aria-live="polite">
					Hi, I’m Walt. I’ll guide you through this demo and explain what’s
					happening as we go.
				</p>
			</div>
		</main>
	);
}
