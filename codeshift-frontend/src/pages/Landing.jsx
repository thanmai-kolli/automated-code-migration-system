import Footer from "../components/layout/Footer";

import Hero from "../components/landing/Hero";
import DemoSection from "../components/landing/DemoSection";
import Features from "../components/landing/Features";
import HowItWorks from "../components/landing/HowItWorks";
import CTA from "../components/landing/CTA";

export default function Landing() {
  return (
    <>
      {/* <Navbar /> */}
      <Hero />
      <DemoSection />
      <Features />
      <HowItWorks />
      <CTA />
      <Footer />
    </>
  );
}