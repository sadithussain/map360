import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Route, Routes } from "react-router-dom";
import Navbar from "./components/Navbar";
import { WorldMap } from "./components/WorldMap";
import Register from "./pages/Register";
import Login from "./pages/Login";
import About from "./pages/About";
import { clearAuthToken, isLoggedIn, onAuthChange } from "./lib/auth";

function App() {
  const navigate = useNavigate();
  const [loggedIn, setLoggedIn] = useState(isLoggedIn());

  useEffect(() => {
    return onAuthChange(() => setLoggedIn(isLoggedIn()));
  }, []);

  function handleLogout() {
    clearAuthToken();
    navigate("/login");
  }

  return (
    <div className="flex h-screen flex-col">
      <header>
        <Navbar loggedIn={loggedIn} onLogout={handleLogout} />
      </header>
      <main className="min-h-0 flex-1">
        <Routes>
          <Route path="/" element={<WorldMap />} />
          <Route path="/register" element={<Register />} />
          <Route path="/login" element={<Login />} />
          <Route path="/about" element={<About />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
