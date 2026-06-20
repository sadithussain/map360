import { Link } from "react-router-dom";

type NavbarProps = {
  loggedIn: boolean;
  onLogout: () => void;
};

function Navbar({ loggedIn, onLogout }: NavbarProps) {
    return (
        <nav className="flex items-center justify-between px-6 py-4 shadow-md">
            <Link to="/" className="text-xl font-bold">Map360</Link>
            <ul className="flex items-center gap-8">
                <li>
                    <Link to="/about">About</Link>
                </li>
                {loggedIn ? (
                    <li>
                        <button
                            type="button"
                            onClick={onLogout}
                            className="hover:cursor-pointer"
                        >
                            Logout
                        </button>
                    </li>
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
