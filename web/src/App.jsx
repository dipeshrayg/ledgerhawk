import { Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Home } from "./pages/Home";
import { Terms, Privacy, Cookies } from "./pages/Legal";
import { Dashboard } from "./pages/Dashboard";
import { VendorDetail } from "./pages/VendorDetail";
import { Calendar } from "./pages/Calendar";
import { VersionDiff } from "./pages/VersionDiff";
import { PreSignReview } from "./pages/PreSignReview";

function App() {
  return (
    <Routes>
      <Route index element={<Home />} />
      <Route path="terms" element={<Terms />} />
      <Route path="privacy" element={<Privacy />} />
      <Route path="cookies" element={<Cookies />} />
      <Route path="app" element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="vendors/:vendorId" element={<VendorDetail />} />
        <Route path="calendar" element={<Calendar />} />
        <Route path="diff/:pairId" element={<VersionDiff />} />
        <Route path="presign/:proposalId" element={<PreSignReview />} />
      </Route>
    </Routes>
  );
}

export default App;
