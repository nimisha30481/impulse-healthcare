import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/primitives";

/** Home page: the DoseWISE line and one way in. */
export default function Landing() {
  return (
    <section className="relative flex min-h-[calc(100vh-4rem)] items-center overflow-hidden">
      <div className="grid-bg pointer-events-none absolute inset-0 [mask-image:radial-gradient(ellipse_at_center,black_30%,transparent_70%)]" />
      <div className="pointer-events-none absolute left-1/2 top-1/2 h-[520px] w-[min(900px,100vw)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-mint/50 blur-3xl dark:bg-primary/20" />
      <div className="container-page relative py-16 text-center">
        <motion.h1 initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}
          className="mx-auto max-w-4xl break-words text-[clamp(22px,9vw,40px)] font-extrabold leading-[1.1] text-ink sm:text-[56px] lg:text-[68px]">
          Better medication management.{" "}
          <span className="bg-gradient-to-r from-primary via-[#1f8a83] to-[#3fae9a] bg-clip-text text-transparent">More connected care.</span>
        </motion.h1>
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15, duration: 0.6 }} className="mt-10">
          <Link to="/register"><Button size="lg" icon={<ArrowRight className="h-5 w-5" />} className="flex-row-reverse px-8">Get Started</Button></Link>
        </motion.div>
      </div>
    </section>
  );
}
