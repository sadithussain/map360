import { Route, Routes } from "react-router-dom";
import Navbar from "./components/Navbar";
import {
  ProtectedRoute,
  PublicOnlyRoute,
} from "./components/ProtectedRoute";
import { WorldMap } from "./components/WorldMap";
import { AppProvider } from "./context/AppContext";
import About from "./pages/About";
import AppShell from "./pages/AppShell";
import Groups from "./pages/Groups";
import Login from "./pages/Login";
import Register from "./pages/Register";

function App() {
  return (
    <AppProvider>
      <div className="flex h-screen flex-col">
        <header>
          <Navbar />
        </header>
        <main className="flex min-h-0 flex-1 flex-col">
          <Routes>
            <Route path="/" element={<WorldMap />} />
            <Route path="/about" element={<About />} />
            <Route
              path="/login"
              element={
                <PublicOnlyRoute>
                  <Login />
                </PublicOnlyRoute>
              }
            />
            <Route
              path="/register"
              element={
                <PublicOnlyRoute>
                  <Register />
                </PublicOnlyRoute>
              }
            />
            <Route
              path="/groups"
              element={
                <ProtectedRoute>
                  <Groups />
                </ProtectedRoute>
              }
            />
            <Route
              path="/app"
              element={
                <ProtectedRoute requireActiveGroup>
                  <AppShell />
                </ProtectedRoute>
              }
            />
          </Routes>
        </main>
      </div>
    </AppProvider>
  );
}

export default App;
