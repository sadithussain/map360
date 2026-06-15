import { Link } from "react-router-dom";

function Navbar() {
    return (
        <nav className="flex items-center justify-between px-6 py-4">
            <div className="text-xl font-bold">Map360</div>
            <ul className="flex items-center gap-8">
                <li>
                    <Link to="/about">About</Link>
                </li>
                <li>
                    <Link to="/register">Register</Link>
                </li>
                <li>
                    <Link to="/login">Login</Link>
                </li>
            </ul>
        </nav>
    );
}

export default Navbar;
