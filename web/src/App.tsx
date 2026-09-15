import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Vendors from "./pages/Vendors";
import Invoices from "./pages/Invoices";
import Payments from "./pages/Payments";
import Alerts from "./pages/Alerts";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/vendors" replace />} />
        <Route path="/vendors" element={<Vendors />} />
        <Route path="/invoices" element={<Invoices />} />
        <Route path="/payments" element={<Payments />} />
        <Route path="/alerts" element={<Alerts />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
