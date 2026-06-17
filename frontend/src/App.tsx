import { Route, Routes } from "react-router-dom";
import Navbar from "./components/Navbar";
import { WorldMap } from "./components/WorldMap";
import Register from "./pages/Register";
import Login from "./pages/Login";

function App() {
  return (
    <div className="flex h-screen flex-col">
      <header>
        <Navbar />
      </header>
      <main className="min-h-0 flex-1">
        <Routes>
          <Route path="/" element={<WorldMap />} />
          <Route path="/register" element={<Register />} />
          <Route path="/login" element={<Login />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
