import Navbar from "./components/Navbar";
import { WorldMap } from "./components/WorldMap";

function App() {
  return (
    <div className="flex h-screen flex-col">
      <header>
        <Navbar />
      </header>
      <main className="min-h-0 flex-1">
        <WorldMap />
      </main>
    </div>
  );
}

export default App;
