
import { motion } from "motion/react";
import {
  ArrowRight,
  Github,
  ShieldCheck,
  Code2,
  GitBranch,
  ScanSearch,
  Zap,
  Upload,
  CheckCircle2,
  Menu,
} from "lucide-react";

const features = [
  {
    icon: ScanSearch,
    number: "01",
    title: "Requirement Analysis",
    description:
      "Turn your software requirements into clear, traceable checkpoints.",
  },
  {
    icon: GitBranch,
    number: "02",
    title: "Code Traceability",
    description:
      "Discover which files and code sections provide evidence for each requirement.",
  },
  {
    icon: ShieldCheck,
    number: "03",
    title: "Implementation Verification",
    description:
      "Understand what is implemented, partially implemented, missing or not verified.",
  },
];

function App() {
  return (
    <div className="min-h-screen overflow-hidden bg-[#080b14] text-white">
      {/* Background effects */}
      <div className="pointer-events-none fixed inset-0 -z-0">
        <div className="absolute -top-40 left-1/4 h-96 w-96 rounded-full bg-violet-600/15 blur-[130px]" />
        <div className="absolute top-80 right-0 h-96 w-96 rounded-full bg-cyan-500/10 blur-[130px]" />
        <div className="grid-background absolute inset-0 opacity-20" />
      </div>

      {/* Navigation */}
      <nav className="relative z-10 mx-auto flex max-w-7xl items-center justify-between px-6 py-6 lg:px-12">
        <a href="#" className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-violet-400/30 bg-violet-500/15">
            <Code2 className="h-6 w-6 text-violet-300" />
          </div>
          <span className="text-xl font-bold tracking-tight">
            Spec<span className="text-violet-400">Trace</span>
          </span>
        </a>

        <div className="hidden items-center gap-9 text-sm text-slate-400 md:flex">
          <a href="#features" className="transition hover:text-white">
            Features
          </a>
          <a href="#workflow" className="transition hover:text-white">
            How it works
          </a>
          <a href="#about" className="transition hover:text-white">
            About
          </a>
        </div>

        <a
          href="#get-started"
          className="hidden items-center gap-2 rounded-lg border border-violet-400/30 bg-violet-500/10 px-5 py-2.5 text-sm font-medium text-violet-200 transition hover:bg-violet-500/20 sm:flex"
        >
          Get started <ArrowRight size={16} />
        </a>

        <button className="rounded-lg border border-white/10 p-2 md:hidden">
          <Menu size={21} />
        </button>
      </nav>

      {/* Hero section */}
      <main className="relative z-10">
        <section
          id="get-started"
          className="mx-auto grid max-w-7xl items-center gap-14 px-6 pb-24 pt-20 lg:grid-cols-2 lg:px-12 lg:pb-32 lg:pt-28"
        >
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
          >
            <div className="mb-8 inline-flex items-center gap-2 rounded-full border border-violet-400/20 bg-violet-400/10 px-4 py-2 text-xs font-medium tracking-wide text-violet-200">
              <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-400" />
              SOFTWARE REQUIREMENT INTELLIGENCE
            </div>

            <h1 className="max-w-2xl text-5xl font-bold leading-[1.12] tracking-tight sm:text-6xl lg:text-7xl">
              Does your code
              <br />
              actually meet
              <br />
              <span className="gradient-text">the specs?</span>
            </h1>

            <p className="mt-8 max-w-xl text-base leading-8 text-slate-400 sm:text-lg">
              Stop guessing. Start verifying. SpecTrace connects software
              requirements to code evidence, helping you understand what your
              project really implements.
            </p>

            <div className="mt-10 flex flex-wrap gap-4">
              <a
                href="#workflow"
                className="group flex items-center gap-3 rounded-xl bg-violet-600 px-6 py-4 font-semibold shadow-lg shadow-violet-600/25 transition hover:-translate-y-1 hover:bg-violet-500"
              >
                Explore SpecTrace
                <ArrowRight
                  size={18}
                  className="transition group-hover:translate-x-1"
                />
              </a>

              <a
                href="#features"
                className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/[0.04] px-6 py-4 font-semibold text-slate-200 transition hover:border-violet-400/40 hover:bg-white/[0.08]"
              >
                Discover features
              </a>
            </div>

            <div className="mt-12 flex flex-wrap gap-7 text-sm text-slate-500">
              <span className="flex items-center gap-2">
                <CheckCircle2 size={16} className="text-emerald-400" />
                Requirement-focused
              </span>
              <span className="flex items-center gap-2">
                <CheckCircle2 size={16} className="text-emerald-400" />
                Code evidence
              </span>
            </div>
          </motion.div>

          {/* Animated analysis visual */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 1, delay: 0.2 }}
            className="relative mx-auto w-full max-w-xl"
          >
            <div className="absolute inset-10 rounded-full bg-violet-600/20 blur-[90px]" />

            <div className="relative rounded-3xl border border-white/10 bg-[#101626]/90 p-5 shadow-2xl shadow-violet-950/40 backdrop-blur-xl sm:p-7">
              <div className="flex items-center justify-between border-b border-white/10 pb-5">
                <div>
                  <p className="text-sm font-semibold text-white">
                    Requirement Intelligence
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    SpecTrace analysis workspace
                  </p>
                </div>
                <div className="rounded-lg border border-emerald-400/20 bg-emerald-400/10 px-3 py-1.5 text-xs text-emerald-300">
                  DEMO PREVIEW
                </div>
              </div>

              <div className="my-7 space-y-4">
                <div className="rounded-xl border border-violet-400/20 bg-violet-400/[0.07] p-4">
                  <div className="mb-3 flex items-center gap-2 text-xs text-violet-300">
                    <ScanSearch size={15} />
                    SOFTWARE REQUIREMENT
                  </div>
                  <p className="text-sm leading-6 text-slate-200">
                    The system shall allow users to securely log in using
                    their registered email.
                  </p>
                </div>

                <div className="flex justify-center">
                  <div className="h-8 w-px bg-gradient-to-b from-violet-400 to-cyan-400" />
                </div>

                <div className="rounded-xl border border-cyan-400/20 bg-cyan-400/[0.06] p-4">
                  <div className="mb-3 flex items-center gap-2 text-xs text-cyan-300">
                    <Code2 size={15} />
                    SOURCE CODE EVIDENCE
                  </div>
                  <div className="rounded-lg bg-[#080d18] p-3 font-mono text-xs leading-6">
                    <p className="text-slate-500"># authentication.py</p>
                    <p>
                      <span className="text-violet-300">def</span>{" "}
                      <span className="text-cyan-300">login</span>
                      <span className="text-slate-300">(email, password):</span>
                    </p>
                    <p className="pl-4 text-emerald-300">
                      verify_credentials(email, password)
                    </p>
                    <p className="pl-4 text-slate-300">...</p>
                  </div>
                </div>

                <div className="flex justify-center">
                  <div className="h-8 w-px bg-gradient-to-b from-cyan-400 to-emerald-400" />
                </div>

                <div className="flex items-center justify-between rounded-xl border border-emerald-400/20 bg-emerald-400/[0.07] p-4">
                  <div className="flex items-center gap-3">
                    <div className="rounded-lg bg-emerald-400/10 p-2">
                      <ShieldCheck className="text-emerald-400" size={21} />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-white">
                        Traceability result
                      </p>
                      <p className="mt-1 text-xs text-slate-400">
                        Illustrative interface preview
                      </p>
                    </div>
                  </div>
                  <span className="rounded-full bg-emerald-400/10 px-3 py-1.5 text-xs text-emerald-300">
                    Example
                  </span>
                </div>
              </div>

              <div className="flex items-center justify-between border-t border-white/10 pt-4 text-xs text-slate-500">
                <span>Requirement → Code → Evidence</span>
                <span className="flex items-center gap-1 text-violet-300">
                  <Zap size={13} /> Traceability
                </span>
              </div>
            </div>

            <motion.div
              animate={{ y: [0, -10, 0] }}
              transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
              className="absolute -right-4 top-16 hidden rounded-xl border border-violet-400/20 bg-[#17172a] p-3 shadow-xl sm:block"
            >
              <GitBranch className="text-violet-300" size={22} />
            </motion.div>

            <motion.div
              animate={{ y: [0, 10, 0] }}
              transition={{ duration: 5, repeat: Infinity, ease: "easeInOut" }}
              className="absolute -bottom-5 -left-4 hidden rounded-xl border border-cyan-400/20 bg-[#10202a] p-3 shadow-xl sm:block"
            >
              <ShieldCheck className="text-cyan-300" size={22} />
            </motion.div>
          </motion.div>
        </section>

        {/* Features */}
        <section
          id="features"
          className="border-t border-white/[0.08] bg-white/[0.015] px-6 py-24 lg:px-12"
        >
          <div className="mx-auto max-w-7xl">
            <div className="mx-auto mb-16 max-w-2xl text-center">
              <p className="text-sm font-semibold tracking-[0.25em] text-violet-400">
                WHAT WE DO
              </p>
              <h2 className="mt-4 text-3xl font-bold sm:text-4xl">
                From requirements to
                <span className="gradient-text"> evidence.</span>
              </h2>
              <p className="mt-5 leading-7 text-slate-400">
                A clearer way to understand the relationship between what
                software should do and what its code actually contains.
              </p>
            </div>

            <div className="grid gap-5 md:grid-cols-3">
              {features.map((feature, index) => {
                const Icon = feature.icon;

                return (
                  <motion.div
                    key={feature.number}
                    initial={{ opacity: 0, y: 25 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.5, delay: index * 0.15 }}
                    className="group rounded-2xl border border-white/10 bg-[#101626]/70 p-7 transition duration-300 hover:-translate-y-2 hover:border-violet-400/40 hover:bg-[#151c30]"
                  >
                    <div className="mb-8 flex items-center justify-between">
                      <div className="rounded-xl border border-violet-400/20 bg-violet-400/10 p-3">
                        <Icon className="text-violet-300" size={25} />
                      </div>
                      <span className="font-mono text-sm text-slate-600">
                        /{feature.number}
                      </span>
                    </div>

                    <h3 className="text-xl font-semibold">
                      {feature.title}
                    </h3>
                    <p className="mt-4 text-sm leading-7 text-slate-400">
                      {feature.description}
                    </p>
                  </motion.div>
                );
              })}
            </div>
          </div>
        </section>

        {/* Workflow */}
        <section id="workflow" className="px-6 py-24 lg:px-12">
          <div className="mx-auto max-w-5xl rounded-3xl border border-violet-400/20 bg-gradient-to-br from-violet-500/[0.12] via-[#101626] to-cyan-500/[0.06] px-7 py-14 text-center sm:px-14">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl border border-violet-300/20 bg-violet-400/10">
              <Upload className="text-violet-300" size={26} />
            </div>
            <h2 className="mt-7 text-3xl font-bold sm:text-4xl">
              Ready to inspect your project?
            </h2>
            <p className="mx-auto mt-5 max-w-xl leading-7 text-slate-400">
              Upload your project, provide its requirements and explore the
              relationship between your specifications and source code.
            </p>
            <button
              onClick={() =>
                alert("Project upload will be connected to the backend in a later step.")
              }
              className="mt-8 inline-flex items-center gap-3 rounded-xl bg-violet-600 px-7 py-4 font-semibold shadow-lg shadow-violet-600/20 transition hover:-translate-y-1 hover:bg-violet-500"
            >
              Start your analysis <ArrowRight size={18} />
            </button>
            <p className="mt-4 text-xs text-slate-500">
              Upload and analysis functionality will be connected in the next
              development stages.
            </p>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer
        id="about"
        className="relative z-10 border-t border-white/10 px-6 py-8 lg:px-12"
      >
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 sm:flex-row">
          <div className="flex items-center gap-2 font-semibold">
            <Code2 className="text-violet-400" size={19} />
            SpecTrace
          </div>
          <p className="text-center text-xs text-slate-500">
            Making software requirements traceable.
          </p>
          <a
            href="#"
            className="flex items-center gap-2 text-sm text-slate-400 transition hover:text-white"
          >
            <Github size={17} /> Project
          </a>
        </div>
      </footer>
    </div>
  );
}

export default App;
