import { Link } from "react-router-dom";
import { useApp } from "../context/AppContext";

function Navbar() {
  const { user, activeGroup, logout } = useApp();
  const loggedIn = user !== null;

  return (
    <nav className="flex items-center justify-between px-6 py-4 shadow-md">
      <Link to="/" className="text-xl font-bold">
        Map360
      </Link>
      <ul className="flex items-center gap-6">
        <li>
          <Link to="/about">About</Link>
        </li>
        {loggedIn ? (
          <>
            <li className="hidden text-sm text-gray-600 sm:block">
              {user.username}
              {activeGroup ? (
                <span className="text-gray-400"> · {activeGroup.name}</span>
              ) : null}
            </li>
            <li>
              <Link to="/groups">Groups</Link>
            </li>
            {activeGroup && (
              <li>
                <Link to="/app">Workspace</Link>
              </li>
            )}
            <li>
              <button
                type="button"
                onClick={logout}
                className="hover:cursor-pointer"
              >
                Logout
              </button>
            </li>
          </>
        ) : (
          <>
            <li>
              <Link to="/register">Register</Link>
            </li>
            <li>
              <Link to="/login">Login</Link>
            </li>
          </>
        )}
      </ul>
    </nav>
  );
}

export default Navbar;
