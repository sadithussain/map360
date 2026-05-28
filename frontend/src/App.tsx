import { WorldMap } from "./components/WorldMap";
import "./App.css";

function App() {
  return (
    <div className="app">
      <header className="app__header">
        <span className="app__brand">Map360</span>
        <span className="app__tagline">Collaborative 3D world mapping</span>
      </header>
      <main className="app__canvas">
        <WorldMap />
      </main>
    </div>
  );
}

export default App;
