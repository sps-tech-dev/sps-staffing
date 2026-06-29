"use client";
/* eslint-disable @next/next/no-img-element, react/no-unescaped-entities */
import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import {
  Users, BookOpen, Monitor, ArrowRight, CheckCircle, Star,
  Phone, Mail, Linkedin, Twitter, Briefcase, GraduationCap,
  Code2, TrendingUp, Globe, Clock, Shield, Zap, Menu, X, Send,
  Brain, Database, Cloud, BarChart3, Target, UserCheck, FileText,
  MessageSquare, Video, Handshake, ChevronRight, MapPin, Building2,
  Lightbulb, Rocket, HeartHandshake, BadgeCheck, Search,
  Instagram, Facebook, ArrowUpRight, Quote, FlaskConical, Cpu,
  RefreshCcw, Smartphone
} from "lucide-react";

// ── Scroll to top on route change ──────────────────────────────────────────
// ── Shared fade-in wrapper ──────────────────────────────────────────────────
export function FadeIn({ children, delay = 0, className = "" }: { children: React.ReactNode; delay?: number; className?: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.6, delay, ease: "easeOut" }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

// ── Navbar ──────────────────────────────────────────────────────────────────
export function Navbar() {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const pathname = usePathname();

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => { setOpen(false); }, [pathname]);

  const links = [
    { to: "/", label: "Home" },
    { to: "/services", label: "Services" },
    { to: "/career", label: "Careers" },
    { to: "/contact", label: "Contact" },
    { to: "/about", label: "About" },
  ];

  return (
    <nav className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${scrolled ? "bg-white shadow-md" : "bg-white/95 backdrop-blur-sm"}`} style={{ fontFamily: "'Outfit', sans-serif" }}>
      <div className="max-w-7xl mx-auto px-6 flex items-center justify-between h-16">
        <Link href="/" className="flex items-center">
          <img src="/sps-logo-horizontal-1920.png" alt="SPSTechnosoft" className="h-9 w-auto" />
        </Link>

        <div className="hidden md:flex items-center gap-1">
          {links.map(l => {
            const isActive = l.to === "/" ? pathname === "/" : pathname.startsWith(l.to);
            return (
              <Link
                key={l.to}
                href={l.to}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${isActive ? "text-[#1A56DB] bg-[#E8EFFE]" : "text-[#0A1628] hover:bg-[#F0F4FA]"}`}
              >
                {l.label}
              </Link>
            );
          })}
        </div>

        <button onClick={() => setOpen(!open)} className="md:hidden p-2 rounded-lg hover:bg-[#F0F4FA]">
          {open ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>

      {open && (
        <div className="md:hidden border-t border-[#DDE4F0] bg-white px-6 py-4 flex flex-col gap-1">
          {links.map(l => (
            <Link key={l.to} href={l.to} className="px-4 py-2.5 rounded-lg text-sm font-medium text-[#0A1628] hover:bg-[#F0F4FA]">{l.label}</Link>
          ))}
        </div>
      )}
    </nav>
  );
}

// ── Footer ──────────────────────────────────────────────────────────────────
export function Footer() {
  return (
    <footer style={{ background: "#0A1628", fontFamily: "'DM Sans', sans-serif" }} className="text-white">
      <div className="max-w-7xl mx-auto px-6 py-16">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-10">
          <div>
            <div className="flex items-center gap-2.5 mb-4">
              <img src="/sps-logo-mark-512.png" alt="" aria-hidden className="w-9 h-9" />
              <span className="text-xl font-bold" style={{ fontFamily: "'Outfit', sans-serif" }}>SPSTechnosoft</span>
            </div>
            <p className="text-sm leading-relaxed" style={{ color: "#8FA3C0" }}>
              Empowering organizations with talent, technology, and training — one solution at a time.
            </p>
            <div className="flex gap-3 mt-5">
              {[Linkedin, Twitter, Instagram, Facebook].map((Icon, i) => (
                <a key={i} href="#" className="w-9 h-9 rounded-lg flex items-center justify-center transition-all duration-200 hover:bg-[#1A56DB]" style={{ background: "rgba(255,255,255,0.08)" }}>
                  <Icon size={15} />
                </a>
              ))}
            </div>
          </div>

          <div>
            <h4 className="font-semibold mb-4 text-sm tracking-wider uppercase" style={{ color: "#8FA3C0" }}>Services</h4>
            <ul className="space-y-2.5">
              {[
                ["Staffing & Recruitment", "/services/staffing"],
                ["Education & Training", "/services/education"],
                ["IT Services & Consulting", "/services/it"],
                ["Internship Programme", "/career"],
                ["Remote Hiring", "/career"],
              ].map(([label, to]) => (
                <li key={label}>
                  <Link href={to} className="text-sm transition-colors duration-200 hover:text-white" style={{ color: "#8FA3C0" }}>{label}</Link>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h4 className="font-semibold mb-4 text-sm tracking-wider uppercase" style={{ color: "#8FA3C0" }}>Company</h4>
            <ul className="space-y-2.5">
              {[
                ["About Us", "/about"],
                ["Our Team", "/about"],
                ["Careers", "/career"],
                ["Contact Us", "/contact"],
                ["Privacy Policy", "/contact"],
              ].map(([label, to]) => (
                <li key={label}>
                  <Link href={to} className="text-sm transition-colors duration-200 hover:text-white" style={{ color: "#8FA3C0" }}>{label}</Link>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h4 className="font-semibold mb-4 text-sm tracking-wider uppercase" style={{ color: "#8FA3C0" }}>Contact</h4>
            <ul className="space-y-3">
              <li className="flex items-start gap-3">
                <Mail size={15} className="mt-0.5 shrink-0" style={{ color: "#1A56DB" }} />
                <span className="text-sm" style={{ color: "#8FA3C0" }}>hello@stratumgroup.in</span>
              </li>
              <li className="flex items-start gap-3">
                <Phone size={15} className="mt-0.5 shrink-0" style={{ color: "#1A56DB" }} />
                <span className="text-sm" style={{ color: "#8FA3C0" }}>+91 98765 43210</span>
              </li>
              <li className="flex items-start gap-3">
                <MapPin size={15} className="mt-0.5 shrink-0" style={{ color: "#1A56DB" }} />
                <span className="text-sm" style={{ color: "#8FA3C0" }}>Bengaluru, India — serving clients globally</span>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-12 pt-8 flex flex-col md:flex-row items-center justify-between gap-4" style={{ borderTop: "1px solid rgba(255,255,255,0.08)" }}>
          <p className="text-xs" style={{ color: "#5A6B8A" }}>© 2024 SPSTechnosoft Group Pvt. Ltd. All rights reserved.</p>
          <p className="text-xs" style={{ color: "#5A6B8A" }}>Staffing · Education · IT Consulting</p>
        </div>
      </div>
    </footer>
  );
}

// ── HOME PAGE ───────────────────────────────────────────────────────────────
export function HomePage() {
  const stats = [
    { value: "600+", label: "Candidates Placed", icon: UserCheck },
    { value: "180+", label: "Enterprise Clients", icon: Building2 },
    { value: "250+", label: "IT Projects Delivered", icon: Code2 },
    { value: "60+", label: "College Partners", icon: GraduationCap },
  ];

  const testimonials = [
    {
      quote: "SPSTechnosoft filled three senior engineering roles for us in under three weeks. The candidates were technically sharp and culture-fit from day one. We couldn't have scaled our product team without them.",
      name: "Priya Nair",
      role: "CTO, Finlatics Technologies",
      rating: 5,
      avatar: "PN",
    },
    {
      quote: "Their EdTech internship programme brought us three interns who are now full-time hires. The live-project experience they had before joining meant zero ramp-up time. Remarkable programme.",
      name: "Arjun Mehta",
      role: "Head of Engineering, NovaBuild",
      rating: 5,
      avatar: "AM",
    },
    {
      quote: "SPSTechnosoft's IT consulting team re-architected our data pipeline with an AI layer that cut processing time by 70%. Professional, deadline-driven, and genuinely invested in our success.",
      name: "Sneha Pillai",
      role: "VP Operations, LogiCore India",
      rating: 5,
      avatar: "SP",
    },
  ];

  const values = [
    { icon: Shield, title: "Trust First", desc: "Every placement and project is backed by accountability and transparency." },
    { icon: Zap, title: "Speed & Precision", desc: "We move fast without compromising on quality or fit." },
    { icon: Brain, title: "AI-Augmented", desc: "Our internal tools leverage AI to surface better matches, faster." },
    { icon: HeartHandshake, title: "Long-Term Partnership", desc: "We measure success in years, not transactions." },
  ];

  const clients = ["TechMahindra", "Infosys BPM", "KPMG India", "Byju's", "Razorpay", "Zepto", "upGrad", "Meesho"];

  return (
    <div style={{ fontFamily: "'DM Sans', sans-serif" }}>

      {/* ── Hero ── */}
      <section className="relative min-h-screen flex items-center overflow-hidden pt-16" style={{ background: "linear-gradient(135deg, #0A1628 0%, #0D2150 60%, #112068 100%)" }}>
        <div className="absolute inset-0 opacity-10" style={{ backgroundImage: "radial-gradient(circle at 20% 80%, #1A56DB 0%, transparent 50%), radial-gradient(circle at 80% 20%, #2563EB 0%, transparent 50%)" }} />
        <div className="absolute inset-0" style={{ backgroundImage: "url(\"data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.03'%3E%3Ccircle cx='30' cy='30' r='1'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E\")" }} />

        <div className="max-w-7xl mx-auto px-6 py-20 grid grid-cols-1 lg:grid-cols-2 gap-16 items-center relative z-10">
          <div>
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}
              className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-semibold mb-6"
              style={{ background: "rgba(26, 86, 219, 0.2)", color: "#93BBFF", border: "1px solid rgba(26, 86, 219, 0.3)" }}>
              <Zap size={12} />
              Staffing · Education · IT Consulting
            </motion.div>

            <motion.h1 initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.1 }}
              className="text-5xl lg:text-6xl font-extrabold text-white leading-tight tracking-tight mb-6"
              style={{ fontFamily: "'Outfit', sans-serif" }}>
              We Build Teams,<br />
              <span style={{ color: "#93BBFF" }}>Skills</span> & Systems<br />
              That <span style={{ background: "linear-gradient(90deg, #1A56DB, #60A5FA)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>Scale.</span>
            </motion.h1>

            <motion.p initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.2 }}
              className="text-lg leading-relaxed mb-8 max-w-lg"
              style={{ color: "#8FA3C0" }}>
              SPSTechnosoft Group connects top talent with growing organizations, equips students with industry-ready skills, and delivers technology consulting that transforms businesses.
            </motion.p>

            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.8, delay: 0.5 }}
              className="flex items-center gap-6 mt-10">
              <div className="flex -space-x-2">
                {["SK", "RM", "AT", "PV"].map((initials, i) => (
                  <div key={i} className="w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold text-white border-2"
                    style={{ background: ["#1A56DB", "#2563EB", "#3B82F6", "#60A5FA"][i], borderColor: "#0A1628" }}>
                    {initials}
                  </div>
                ))}
              </div>
              <div>
                <div className="flex gap-0.5 mb-0.5">
                  {[...Array(5)].map((_, i) => <Star key={i} size={13} fill="#F59E0B" color="#F59E0B" />)}
                </div>
                <p className="text-xs" style={{ color: "#8FA3C0" }}>Trusted by 180+ organizations</p>
              </div>
            </motion.div>
          </div>

          <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.8, delay: 0.2 }}
            className="hidden lg:block relative">
            <div className="relative rounded-2xl overflow-hidden shadow-2xl" style={{ aspectRatio: "4/3" }}>
              <img src="https://images.unsplash.com/photo-1600880292203-757bb62b4baf?w=800&h=600&fit=crop&auto=format"
                alt="Professional team collaboration in a modern office" className="w-full h-full object-cover" />
              <div className="absolute inset-0" style={{ background: "linear-gradient(to bottom, transparent 60%, rgba(10,22,40,0.4))" }} />
            </div>

            <div className="absolute -bottom-6 -left-6 bg-white rounded-2xl shadow-xl p-4 flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: "#E8EFFE" }}>
                <BadgeCheck size={20} style={{ color: "#1A56DB" }} />
              </div>
              <div>
                <p className="text-xs font-semibold" style={{ color: "#0A1628" }}>Avg. Placement Time</p>
                <p className="text-lg font-bold" style={{ color: "#1A56DB" }}>30 Days</p>
              </div>
            </div>

            <div className="absolute -top-4 -right-4 bg-white rounded-2xl shadow-xl p-4 flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: "#FEF3C7" }}>
                <TrendingUp size={20} style={{ color: "#D97706" }} />
              </div>
              <div>
                <p className="text-xs font-semibold" style={{ color: "#0A1628" }}>Client Retention</p>
                <p className="text-lg font-bold" style={{ color: "#D97706" }}>98%</p>
              </div>
            </div>
          </motion.div>
        </div>

        <div className="absolute bottom-0 left-0 right-0 h-16" style={{ background: "linear-gradient(to top, #F0F4FA, transparent)" }} />
      </section>

      {/* ── Stats Bar ── */}
      <section className="py-16 bg-white">
        <div className="max-w-7xl mx-auto px-6">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-8">
            {stats.map(({ value, label, icon: Icon }, i) => (
              <FadeIn key={label} delay={i * 0.1}>
                <div className="text-center">
                  <div className="w-12 h-12 rounded-xl mx-auto mb-3 flex items-center justify-center" style={{ background: "#E8EFFE" }}>
                    <Icon size={22} style={{ color: "#1A56DB" }} />
                  </div>
                  <p className="text-4xl font-extrabold mb-1" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>{value}</p>
                  <p className="text-sm" style={{ color: "#5A6B8A" }}>{label}</p>
                </div>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      {/* ── Who We Are ── */}
      <section className="py-24" style={{ background: "#F0F4FA" }}>
        <div className="max-w-7xl mx-auto px-6 grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
          <FadeIn>
            <div className="relative">
              <div className="rounded-2xl overflow-hidden shadow-xl">
                <img src="https://images.unsplash.com/photo-1522202176988-66273c2fd55f?w=700&h=500&fit=crop&auto=format"
                  alt="SPSTechnosoft team working together" className="w-full object-cover" style={{ aspectRatio: "7/5" }} />
              </div>
              <div className="absolute -top-4 -left-4 bg-[#1A56DB] text-white rounded-2xl p-4 shadow-lg">
                <p className="text-3xl font-extrabold" style={{ fontFamily: "'Outfit', sans-serif" }}>7+</p>
                <p className="text-xs opacity-80">Years of Excellence</p>
              </div>
            </div>
          </FadeIn>

          <FadeIn delay={0.2}>
            <div>
              <span className="inline-block text-xs font-bold uppercase tracking-widest mb-3 px-3 py-1 rounded-full" style={{ background: "#E8EFFE", color: "#1A56DB" }}>Who We Are</span>
              <h2 className="text-4xl font-extrabold leading-tight mb-5" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>
                A Growth Partner Across<br />Talent, Learning & Technology
              </h2>
              <p className="text-base leading-relaxed mb-5" style={{ color: "#5A6B8A" }}>
                Founded in 2017, SPSTechnosoft Group is a Bengaluru-based multi-vertical firm that operates at the intersection of human capital and technology. We exist to answer one question for every client: <em>how do you grow faster and smarter?</em>
              </p>
              <p className="text-base leading-relaxed mb-6" style={{ color: "#5A6B8A" }}>
                Whether you need your next engineering hire in 10 days, want to upskill a 200-person workforce, or need a technology partner to modernize your infrastructure — SPSTechnosoft delivers with the same obsession for quality across all three verticals.
              </p>
              <ul className="space-y-3 mb-8">
                {[
                  "Pan-India sourcing network with 80,000+ pre-screened candidate profiles",
                  "AI-powered screening and matching platform for faster, better hires",
                  "Industry-aligned training programmes co-designed with hiring companies",
                  "Dedicated IT consulting pod with expertise in cloud, AI, and digital transformation",
                ].map(item => (
                  <li key={item} className="flex items-start gap-3">
                    <CheckCircle size={18} className="mt-0.5 shrink-0" style={{ color: "#1A56DB" }} />
                    <span className="text-sm" style={{ color: "#5A6B8A" }}>{item}</span>
                  </li>
                ))}
              </ul>
              <Link href="/about" className="inline-flex items-center gap-2 text-sm font-semibold transition-colors duration-200 hover:opacity-70" style={{ color: "#1A56DB" }}>
                Meet Our Leadership Team <ArrowRight size={16} />
              </Link>
            </div>
          </FadeIn>
        </div>
      </section>

      {/* ── What We Deliver ── */}
      <section className="py-24 bg-white">
        <div className="max-w-7xl mx-auto px-6">
          <FadeIn className="text-center mb-14">
            <span className="inline-block text-xs font-bold uppercase tracking-widest mb-3 px-3 py-1 rounded-full" style={{ background: "#E8EFFE", color: "#1A56DB" }}>Our Verticals</span>
            <h2 className="text-4xl font-extrabold mb-4" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>What We Deliver</h2>
            <p className="text-base max-w-xl mx-auto" style={{ color: "#5A6B8A" }}>Three distinct services. One unified commitment to your growth.</p>
          </FadeIn>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {[
              {
                icon: Users,
                title: "Staffing & Recruitment",
                color: "#1A56DB",
                bg: "#E8EFFE",
                image: "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=600&h=400&fit=crop&auto=format",
                desc: "End-to-end talent acquisition across technology, finance, and operations verticals. From sourcing to onboarding, we own the process.",
                points: ["Permanent, Contract & Remote Hiring", "AI-Monitored Pre-Screening", "80K+ Candidate Database", "30-Day Average Placement"],
                to: "/services/staffing",
              },
              {
                icon: BookOpen,
                title: "Education, Training & Internships",
                color: "#059669",
                bg: "#D1FAE5",
                image: "https://images.unsplash.com/photo-1523580494863-6f3031224c94?w=600&h=400&fit=crop&auto=format",
                desc: "From college internships on live projects to enterprise L&D programmes — we build capability at every career stage.",
                points: ["Live Industry Project Experience", "Corporate Upskilling Modules", "EdTech Certification Tracks", "Campus-to-Corporate Pipeline"],
                to: "/services/education",
              },
              {
                icon: Monitor,
                title: "IT Services & Consulting",
                color: "#7C3AED",
                bg: "#EDE9FE",
                image: "https://images.unsplash.com/photo-1518770660439-4636190af475?w=600&h=400&fit=crop&auto=format",
                desc: "Custom software, cloud migrations, AI integration, and digital transformation — engineered for measurable business outcomes.",
                points: ["Custom Software Development", "Cloud & DevOps Solutions", "AI/ML Integration", "Digital Transformation Advisory"],
                to: "/services/it",
              },
            ].map(({ icon: Icon, title, color, bg, image, desc, points, to }, i) => (
              <FadeIn key={title} delay={i * 0.15}>
                <div className="group rounded-2xl overflow-hidden bg-white shadow-md hover:shadow-xl transition-all duration-300 flex flex-col" style={{ border: "1px solid rgba(10,22,40,0.08)" }}>
                  <div className="relative h-48 overflow-hidden">
                    <img src={image} alt={title} className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105" />
                    <div className="absolute inset-0" style={{ background: `linear-gradient(to bottom, transparent 40%, ${color}CC)` }} />
                  </div>
                  <div className="p-6 flex flex-col flex-1">
                    <div className="w-11 h-11 rounded-xl flex items-center justify-center mb-4" style={{ background: bg }}>
                      <Icon size={22} style={{ color }} />
                    </div>
                    <h3 className="text-xl font-bold mb-3" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>{title}</h3>
                    <p className="text-sm leading-relaxed mb-4" style={{ color: "#5A6B8A" }}>{desc}</p>
                    <ul className="space-y-2 mb-6 flex-1">
                      {points.map(p => (
                        <li key={p} className="flex items-center gap-2 text-xs" style={{ color: "#5A6B8A" }}>
                          <div className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: color }} />
                          {p}
                        </li>
                      ))}
                    </ul>
                    <Link href={to} className="inline-flex items-center gap-2 text-sm font-semibold transition-all duration-200 group-hover:gap-3" style={{ color }}>
                      Learn More <ArrowRight size={15} />
                    </Link>
                  </div>
                </div>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      {/* ── Our Customers (continuous right-to-left marquee) ── */}
      <section className="py-20 overflow-hidden" style={{ background: "#0A1628" }}>
        <div className="max-w-7xl mx-auto px-6 text-center">
          <FadeIn>
            <p className="text-sm font-semibold uppercase tracking-widest mb-10" style={{ color: "#5A6B8A" }}>Trusted by industry leaders across sectors</p>
          </FadeIn>
        </div>
        <div className="relative">
          {/* edge fades */}
          <div className="pointer-events-none absolute inset-y-0 left-0 z-10 w-24" style={{ background: "linear-gradient(to right, #0A1628, transparent)" }} />
          <div className="pointer-events-none absolute inset-y-0 right-0 z-10 w-24" style={{ background: "linear-gradient(to left, #0A1628, transparent)" }} />
          {/* track: two identical copies → loops seamlessly at -50% */}
          <div className="marquee-track flex w-max gap-6 will-change-transform">
            {[...clients, ...clients].map((name, i) => (
              <div
                key={i}
                className="shrink-0 rounded-xl px-8 py-4 text-center font-semibold text-sm whitespace-nowrap"
                style={{ background: "rgba(255,255,255,0.05)", color: "#8FA3C0" }}
                aria-hidden={i >= clients.length}
              >
                {name}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Testimonials ── */}
      <section className="py-24" style={{ background: "#F0F4FA" }}>
        <div className="max-w-7xl mx-auto px-6">
          <FadeIn className="text-center mb-14">
            <span className="inline-block text-xs font-bold uppercase tracking-widest mb-3 px-3 py-1 rounded-full" style={{ background: "#E8EFFE", color: "#1A56DB" }}>Client Stories</span>
            <h2 className="text-4xl font-extrabold" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>What Our Clients Say</h2>
          </FadeIn>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {testimonials.map(({ quote, name, role, rating, avatar }, i) => (
              <FadeIn key={name} delay={i * 0.15}>
                <div className="bg-white rounded-2xl p-7 flex flex-col gap-4 shadow-md h-full" style={{ border: "1px solid rgba(10,22,40,0.08)" }}>
                  <Quote size={28} style={{ color: "#E8EFFE" }} />
                  <p className="text-sm leading-relaxed flex-1" style={{ color: "#5A6B8A" }}>{quote}</p>
                  <div className="flex gap-0.5">
                    {[...Array(rating)].map((_, i) => <Star key={i} size={13} fill="#F59E0B" color="#F59E0B" />)}
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full flex items-center justify-center text-xs font-bold text-white" style={{ background: "linear-gradient(135deg, #0A1628, #1A56DB)" }}>
                      {avatar}
                    </div>
                    <div>
                      <p className="text-sm font-bold" style={{ color: "#0A1628" }}>{name}</p>
                      <p className="text-xs" style={{ color: "#5A6B8A" }}>{role}</p>
                    </div>
                  </div>
                </div>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      {/* ── Our Values ── */}
      <section className="py-24 bg-white">
        <div className="max-w-7xl mx-auto px-6">
          <FadeIn className="text-center mb-14">
            <span className="inline-block text-xs font-bold uppercase tracking-widest mb-3 px-3 py-1 rounded-full" style={{ background: "#E8EFFE", color: "#1A56DB" }}>Great Place to Work</span>
            <h2 className="text-4xl font-extrabold mb-4" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>Built on Values That Last</h2>
            <p className="text-base max-w-xl mx-auto" style={{ color: "#5A6B8A" }}>Everything we do is grounded in four core principles that have defined how we operate since day one.</p>
          </FadeIn>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {values.map(({ icon: Icon, title, desc }, i) => (
              <FadeIn key={title} delay={i * 0.1}>
                <div className="rounded-2xl p-6 text-center" style={{ background: "#F0F4FA", border: "1px solid rgba(10,22,40,0.06)" }}>
                  <div className="w-14 h-14 rounded-2xl mx-auto mb-4 flex items-center justify-center" style={{ background: "linear-gradient(135deg, #0A1628, #1A56DB)" }}>
                    <Icon size={24} className="text-white" />
                  </div>
                  <h4 className="font-bold mb-2" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>{title}</h4>
                  <p className="text-sm leading-relaxed" style={{ color: "#5A6B8A" }}>{desc}</p>
                </div>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA Banner ── */}
      <section className="py-20" style={{ background: "linear-gradient(135deg, #0A1628, #1A2F6B)" }}>
        <FadeIn className="max-w-4xl mx-auto px-6 text-center">
          <h2 className="text-4xl font-extrabold text-white mb-4" style={{ fontFamily: "'Outfit', sans-serif" }}>
            Ready to Grow With SPSTechnosoft?
          </h2>
          <p className="text-lg mb-8" style={{ color: "#8FA3C0" }}>
            Whether you're hiring, learning, or building — let's have a conversation about what's possible.
          </p>
          <div className="flex flex-wrap gap-4 justify-center">
            <Link href="/contact" className="inline-flex items-center gap-2 px-7 py-3.5 rounded-xl text-sm font-semibold text-white hover:opacity-90 transition-all" style={{ background: "#1A56DB" }}>
              Start a Conversation <ArrowRight size={16} />
            </Link>
            <Link href="/services" className="inline-flex items-center gap-2 px-7 py-3.5 rounded-xl text-sm font-semibold text-white hover:bg-white/10 transition-all" style={{ border: "1px solid rgba(255,255,255,0.25)" }}>
              Explore Services
            </Link>
          </div>
        </FadeIn>
      </section>
    </div>
  );
}

// ── SERVICES PAGE ───────────────────────────────────────────────────────────
export function ServicesPage() {
  const services = [
    {
      icon: Users,
      title: "Staffing & Recruitment",
      tagline: "The right talent, placed with precision.",
      color: "#1A56DB",
      bg: "#E8EFFE",
      to: "/services/staffing",
      image: "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=800&h=500&fit=crop&auto=format",
      overview: "We help startups and enterprises build high-performance teams through a meticulous, AI-assisted hiring process. Our 80,000+ candidate database and dedicated industry recruiters reduce time-to-hire without compromising on quality.",
      capabilities: [
        { icon: UserCheck, title: "Permanent Hiring", desc: "Full-time placements with 60-day replacement guarantee." },
        { icon: Clock, title: "Contract Staffing", desc: "Flexible staffing for project-based or interim needs." },
        { icon: Globe, title: "Remote Hiring", desc: "Build distributed teams with vetted remote-first talent." },
        { icon: Brain, title: "AI Pre-Screening", desc: "AI-monitored assessments filter top 10% of applicants." },
        { icon: Database, title: "Candidate Database", desc: "80K+ pre-screened profiles across 30+ domains." },
        { icon: BadgeCheck, title: "Quality Guarantee", desc: "Structured interviews and reference checks as standard." },
      ],
    },
    {
      icon: BookOpen,
      title: "Education, Training & Internships",
      tagline: "Building the workforce of tomorrow, today.",
      color: "#059669",
      bg: "#D1FAE5",
      to: "/services/education",
      image: "https://images.unsplash.com/photo-1523580494863-6f3031224c94?w=800&h=500&fit=crop&auto=format",
      overview: "Our EdTech vertical bridges the gap between academic knowledge and industry expectation. College students gain hands-on experience through live organizational projects, while enterprises upskill their teams with structured, outcome-driven L&D programmes.",
      capabilities: [
        { icon: GraduationCap, title: "Internship Programme", desc: "Students work on live client projects, not simulations." },
        { icon: FlaskConical, title: "Skill Bootcamps", desc: "Intensive 8–12 week tracks in tech, data, and management." },
        { icon: Building2, title: "Corporate L&D", desc: "Custom upskilling workshops for enterprise teams." },
        { icon: BadgeCheck, title: "Certification Tracks", desc: "Industry-recognized certifications upon completion." },
        { icon: Rocket, title: "Campus-to-Corporate", desc: "Direct hire pipeline from our training graduates." },
        { icon: Brain, title: "AI-Powered Learning", desc: "Adaptive assessments and personalized learning paths." },
      ],
    },
    {
      icon: Monitor,
      title: "IT Services & Consulting",
      tagline: "Technology solutions built for business outcomes.",
      color: "#7C3AED",
      bg: "#EDE9FE",
      to: "/services/it",
      image: "https://images.unsplash.com/photo-1518770660439-4636190af475?w=800&h=500&fit=crop&auto=format",
      overview: "SPSTechnosoft's IT consulting team brings together software engineers, cloud architects, and AI specialists to help organizations modernize, automate, and scale. We don't just build software — we solve the business problem behind the technology requirement.",
      capabilities: [
        { icon: Code2, title: "Custom Development", desc: "Web, mobile, and enterprise application development." },
        { icon: Cloud, title: "Cloud & DevOps", desc: "AWS, Azure, GCP migrations and CI/CD pipeline setup." },
        { icon: Brain, title: "AI/ML Integration", desc: "Intelligent automation, NLP, and predictive analytics." },
        { icon: BarChart3, title: "Data Engineering", desc: "Pipelines, warehouses, and business intelligence dashboards." },
        { icon: Shield, title: "Security Consulting", desc: "Vulnerability audits, compliance, and secure architecture." },
        { icon: Lightbulb, title: "Digital Strategy", desc: "Technology roadmapping and transformation advisory." },
      ],
    },
  ];

  return (
    <div style={{ fontFamily: "'DM Sans', sans-serif" }}>
      <div className="pt-16" style={{ background: "linear-gradient(135deg, #0A1628, #0D2150)" }}>
        <div className="max-w-7xl mx-auto px-6 py-20 text-center">
          <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.5 }}
            className="inline-block text-xs font-bold uppercase tracking-widest mb-4 px-3 py-1 rounded-full"
            style={{ background: "rgba(26,86,219,0.2)", color: "#93BBFF", border: "1px solid rgba(26,86,219,0.3)" }}>
            Our Services
          </motion.span>
          <motion.h1 initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.1 }}
            className="text-5xl font-extrabold text-white mb-4" style={{ fontFamily: "'Outfit', sans-serif" }}>
            Three Verticals. One Mission.
          </motion.h1>
          <motion.p initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.2 }}
            className="text-lg max-w-2xl mx-auto" style={{ color: "#8FA3C0" }}>
            Explore our service verticals and discover how SPSTechnosoft can accelerate your organization's growth across talent, learning, and technology.
          </motion.p>
        </div>
      </div>

      <div className="bg-white">
        {services.map(({ icon: Icon, title, tagline, color, bg, to, image, overview, capabilities }, idx) => (
          <section key={title} className="py-20" style={{ background: idx % 2 === 0 ? "white" : "#F0F4FA" }}>
            <div className="max-w-7xl mx-auto px-6">
              <div className={`grid grid-cols-1 lg:grid-cols-2 gap-16 items-center ${idx % 2 === 1 ? "lg:grid-flow-dense" : ""}`}>
                <FadeIn className={idx % 2 === 1 ? "lg:col-start-2" : ""}>
                  <div className="rounded-2xl overflow-hidden shadow-xl">
                    <img src={image} alt={title} className="w-full object-cover" style={{ aspectRatio: "16/10" }} />
                  </div>
                </FadeIn>

                <FadeIn delay={0.2} className={idx % 2 === 1 ? "lg:col-start-1 lg:row-start-1" : ""}>
                  <div className="w-12 h-12 rounded-xl flex items-center justify-center mb-5" style={{ background: bg }}>
                    <Icon size={24} style={{ color }} />
                  </div>
                  <h2 className="text-3xl font-extrabold mb-2" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>{title}</h2>
                  <p className="text-sm font-semibold mb-4" style={{ color }}>{tagline}</p>
                  <p className="text-sm leading-relaxed mb-8" style={{ color: "#5A6B8A" }}>{overview}</p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-8">
                    {capabilities.map(({ icon: CIcon, title: ct, desc }) => (
                      <div key={ct} className="flex items-start gap-3 p-3 rounded-xl" style={{ background: bg }}>
                        <CIcon size={18} className="mt-0.5 shrink-0" style={{ color }} />
                        <div>
                          <p className="text-sm font-semibold mb-0.5" style={{ color: "#0A1628" }}>{ct}</p>
                          <p className="text-xs leading-relaxed" style={{ color: "#5A6B8A" }}>{desc}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                  <Link href={to} className="inline-flex items-center gap-2 px-6 py-3 rounded-xl text-sm font-semibold text-white transition-all hover:opacity-90" style={{ background: color }}>
                    Explore {title} <ArrowRight size={16} />
                  </Link>
                </FadeIn>
              </div>
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}

// ── STAFFING DETAIL PAGE ────────────────────────────────────────────────────
export function StaffingPage() {
  const hiringTypes = [
    { type: "Permanent Hiring", icon: Briefcase, color: "#1A56DB", desc: "Long-term placements with a structured fit process and 60-day replacement guarantee. Ideal for core team roles.", features: ["Full lifecycle recruitment", "Culture-fit assessment", "60-day replacement guarantee", "Onboarding support"] },
    { type: "Contract Staffing", icon: Clock, color: "#D97706", desc: "Flexible talent for defined project durations. Pre-vetted professionals available within 5 business days.", features: ["Rapid deployment", "Project-aligned contracts", "Pay-per-use model", "Extension options"] },
    { type: "Remote Hiring", icon: Globe, color: "#059669", desc: "Distributed team building with thorough remote-work capability assessment. Geography is no barrier.", features: ["Remote-first candidates", "Time-zone aligned sourcing", "Communication-skills testing", "Async work readiness check"] },
  ];

  const steps = [
    { step: "01", title: "Requirement Analysis", desc: "We conduct a deep-dive session to understand the role, team culture, technical requirements, and ideal candidate profile.", icon: FileText },
    { step: "02", title: "Sourcing & Database Match", desc: "Our sourcing team queries our 80,000+ candidate database alongside active market channels and referral networks.", icon: Database },
    { step: "03", title: "AI-Monitored Assessment", desc: "Shortlisted candidates complete a role-specific AI-proctored test evaluating technical and cognitive aptitude.", icon: Brain },
    { step: "04", title: "3 Rounds of Interview", desc: "Technical screening, domain panel, and a cross-functional round ensure comprehensive evaluation.", icon: Video },
    { step: "05", title: "Managerial & HR Round", desc: "Final alignment on role expectations, team fit, and compensation structure with the client's leadership.", icon: Handshake },
    { step: "06", title: "Offer & Onboarding", desc: "We coordinate the offer letter, acceptance, and first-day onboarding to ensure a smooth transition.", icon: BadgeCheck },
  ];

  return (
    <div style={{ fontFamily: "'DM Sans', sans-serif" }}>
      <div className="pt-16" style={{ background: "linear-gradient(135deg, #0A1628, #0D2150)" }}>
        <div className="max-w-7xl mx-auto px-6 py-20">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
            <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
              <Link href="/services" className="inline-flex items-center gap-1.5 text-xs font-semibold mb-6 hover:opacity-70" style={{ color: "#93BBFF" }}>
                ← Services
              </Link>
              <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-bold mb-4" style={{ background: "rgba(26,86,219,0.2)", color: "#93BBFF" }}>
                <Users size={12} /> Staffing & Recruitment
              </span>
              <h1 className="text-5xl font-extrabold text-white mb-4 leading-tight" style={{ fontFamily: "'Outfit', sans-serif" }}>
                Hire Better.<br />Hire Faster.
              </h1>
              <p className="text-lg mb-8" style={{ color: "#8FA3C0" }}>
                End-to-end recruitment across permanent, contract, and remote roles — powered by a proprietary candidate database and an AI-assisted screening pipeline.
              </p>
              <div className="flex gap-4">
                <Link href="/contact" className="inline-flex items-center gap-2 px-6 py-3 rounded-xl text-sm font-semibold text-white" style={{ background: "#1A56DB" }}>
                  Hire With Us <ArrowRight size={16} />
                </Link>
              </div>
            </motion.div>
            <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.7, delay: 0.2 }}
              className="hidden lg:grid grid-cols-2 gap-4">
              {[
                { label: "Candidate Database", value: "80K+", icon: Database, color: "#1A56DB" },
                { label: "Avg. Time to Fill", value: "30 Days", icon: Clock, color: "#D97706" },
                { label: "Offer Acceptance Rate", value: "91%", icon: BadgeCheck, color: "#059669" },
                { label: "Roles Placed", value: "600+", icon: UserCheck, color: "#7C3AED" },
              ].map(({ label, value, icon: Icon, color }) => (
                <div key={label} className="rounded-2xl p-5" style={{ background: "rgba(255,255,255,0.07)" }}>
                  <Icon size={22} style={{ color }} className="mb-3" />
                  <p className="text-2xl font-extrabold text-white mb-1" style={{ fontFamily: "'Outfit', sans-serif" }}>{value}</p>
                  <p className="text-xs" style={{ color: "#8FA3C0" }}>{label}</p>
                </div>
              ))}
            </motion.div>
          </div>
        </div>
      </div>

      {/* Portal access — login entry points (routes into the existing auth/portals) */}
      <section className="py-20" style={{ background: "#F0F4FA" }}>
        <div className="max-w-7xl mx-auto px-6">
          <FadeIn className="text-center mb-12">
            <span className="inline-block text-xs font-bold uppercase tracking-widest mb-3 px-3 py-1 rounded-full" style={{ background: "#E8EFFE", color: "#1A56DB" }}>Portal Access</span>
            <h2 className="text-4xl font-extrabold mb-3" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>Sign In to Your Portal</h2>
            <p className="text-base max-w-xl mx-auto" style={{ color: "#5A6B8A" }}>Three roles, three workspaces — all on the secure SPSTechnosoft platform.</p>
          </FadeIn>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              { icon: Building2, title: "Client Login", desc: "Review submissions, run your pipeline, release offers.", href: "/login?role=client", color: "#1A56DB", bg: "#E8EFFE" },
              { icon: UserCheck, title: "Candidate Login", desc: "Track your applications and interview schedule.", href: "/login?role=candidate", color: "#059669", bg: "#D1FAE5" },
              { icon: Briefcase, title: "Employee Login", desc: "Recruiters & staff — manage requisitions and delivery.", href: "/login?role=employee", color: "#7C3AED", bg: "#EDE9FE" },
            ].map(({ icon: Icon, title, desc, href, color, bg }, i) => (
              <FadeIn key={title} delay={i * 0.1}>
                <Link href={href} className="group flex h-full flex-col items-center rounded-2xl bg-white p-7 text-center shadow-md transition-all duration-300 hover:shadow-xl" style={{ border: "1px solid rgba(10,22,40,0.08)" }}>
                  <div className="w-14 h-14 rounded-2xl flex items-center justify-center mb-4" style={{ background: bg }}>
                    <Icon size={26} style={{ color }} />
                  </div>
                  <h3 className="text-xl font-bold mb-2" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>{title}</h3>
                  <p className="text-sm mb-5 flex-1" style={{ color: "#5A6B8A" }}>{desc}</p>
                  <span className="inline-flex w-full items-center justify-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold text-white" style={{ background: color }}>
                    {title} <ArrowRight size={15} />
                  </span>
                </Link>
              </FadeIn>
            ))}
          </div>
          <FadeIn delay={0.15}>
            <div className="mt-8 flex flex-col items-center justify-between gap-4 rounded-2xl p-7 sm:flex-row" style={{ background: "linear-gradient(135deg, #0A1628, #1A56DB)" }}>
              <div className="text-center sm:text-left">
                <h3 className="text-lg font-bold text-white" style={{ fontFamily: "'Outfit', sans-serif" }}>New here? Hiring for a role?</h3>
                <p className="text-sm" style={{ color: "#B9C7E0" }}>Register your company and post your first job — we&apos;ll take it from there.</p>
              </div>
              <Link href="/register/client" className="inline-flex shrink-0 items-center gap-2 whitespace-nowrap rounded-xl px-6 py-3 text-sm font-semibold" style={{ background: "white", color: "#0A1628" }}>
                Post a Job <ArrowRight size={16} />
              </Link>
            </div>
          </FadeIn>
        </div>
      </section>

      {/* Hiring Types */}
      <section className="py-20 bg-white">
        <div className="max-w-7xl mx-auto px-6">
          <FadeIn className="mb-12">
            <h2 className="text-3xl font-extrabold mb-3" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>Hiring Engagements We Support</h2>
            <p className="text-sm" style={{ color: "#5A6B8A" }}>Choose the model that fits your business rhythm.</p>
          </FadeIn>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {hiringTypes.map(({ type, icon: Icon, color, desc, features }, i) => (
              <FadeIn key={type} delay={i * 0.15}>
                <div className="rounded-2xl p-7 h-full flex flex-col" style={{ border: `2px solid ${color}20`, background: `${color}06` }}>
                  <div className="w-12 h-12 rounded-xl flex items-center justify-center mb-4" style={{ background: `${color}18` }}>
                    <Icon size={22} style={{ color }} />
                  </div>
                  <h3 className="text-lg font-bold mb-2" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>{type}</h3>
                  <p className="text-sm leading-relaxed mb-5 flex-1" style={{ color: "#5A6B8A" }}>{desc}</p>
                  <ul className="space-y-2">
                    {features.map(f => (
                      <li key={f} className="flex items-center gap-2 text-xs" style={{ color: "#5A6B8A" }}>
                        <CheckCircle size={13} style={{ color }} />
                        {f}
                      </li>
                    ))}
                  </ul>
                </div>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      {/* Our Database */}
      <section className="py-20" style={{ background: "linear-gradient(135deg, #0A1628, #1A2F6B)" }}>
        <div className="max-w-7xl mx-auto px-6 grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
          <FadeIn>
            <h2 className="text-4xl font-extrabold text-white mb-5" style={{ fontFamily: "'Outfit', sans-serif" }}>
              Our Candidate Database: <br />A Head Start on Every Search
            </h2>
            <p className="text-base mb-6" style={{ color: "#8FA3C0" }}>
              We don't start from scratch on every mandate. Over seven years, we've built a proprietary database of 80,000+ pre-screened candidates across technology, finance, operations, and design — enriched with assessment scores, interview notes, and career trajectory data.
            </p>
            {[
              { label: "Active profiles", value: "80,000+" },
              { label: "Domain coverage", value: "30+ roles" },
              { label: "Verified with assessments", value: "100%" },
              { label: "Updated in last 90 days", value: "62%" },
            ].map(({ label, value }) => (
              <div key={label} className="flex items-center justify-between py-3" style={{ borderBottom: "1px solid rgba(255,255,255,0.08)" }}>
                <span className="text-sm" style={{ color: "#8FA3C0" }}>{label}</span>
                <span className="text-sm font-bold text-white">{value}</span>
              </div>
            ))}
          </FadeIn>
          <FadeIn delay={0.2}>
            <div className="rounded-2xl overflow-hidden shadow-2xl">
              <img src="https://images.unsplash.com/photo-1551434678-e076c223a692?w=700&h=500&fit=crop&auto=format"
                alt="Team reviewing candidate profiles" className="w-full object-cover" style={{ aspectRatio: "7/5" }} />
            </div>
          </FadeIn>
        </div>
      </section>

      {/* Hiring Process */}
      <section className="py-24" style={{ background: "#F0F4FA" }}>
        <div className="max-w-7xl mx-auto px-6">
          <FadeIn className="text-center mb-14">
            <h2 className="text-4xl font-extrabold mb-3" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>Our Hiring Process</h2>
            <p className="text-base max-w-xl mx-auto" style={{ color: "#5A6B8A" }}>A structured, six-step process designed to surface the right candidate — not just any candidate.</p>
          </FadeIn>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {steps.map(({ step, title, desc, icon: Icon }, i) => (
              <FadeIn key={step} delay={i * 0.1}>
                <div className="bg-white rounded-2xl p-6" style={{ border: "1px solid rgba(10,22,40,0.08)" }}>
                  <div className="flex items-start gap-4">
                    <div className="text-4xl font-extrabold leading-none" style={{ fontFamily: "'Outfit', sans-serif", color: "#E8EFFE" }}>{step}</div>
                    <div>
                      <div className="w-9 h-9 rounded-xl flex items-center justify-center mb-3" style={{ background: "#E8EFFE" }}>
                        <Icon size={18} style={{ color: "#1A56DB" }} />
                      </div>
                      <h4 className="font-bold mb-2" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>{title}</h4>
                      <p className="text-sm leading-relaxed" style={{ color: "#5A6B8A" }}>{desc}</p>
                    </div>
                  </div>
                </div>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      <section className="py-16 bg-white text-center">
        <FadeIn>
          <h2 className="text-3xl font-extrabold mb-4" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>Ready to Find Your Next Great Hire?</h2>
          <p className="text-sm mb-6" style={{ color: "#5A6B8A" }}>Share your requirement and our team will reach out within 24 hours.</p>
          <Link href="/contact" className="inline-flex items-center gap-2 px-7 py-3.5 rounded-xl text-sm font-semibold text-white" style={{ background: "#1A56DB" }}>
            Submit a Requirement <ArrowRight size={16} />
          </Link>
        </FadeIn>
      </section>
    </div>
  );
}

// ── EDUCATION DETAIL PAGE ───────────────────────────────────────────────────
export function EducationPage() {
  return (
    <div style={{ fontFamily: "'DM Sans', sans-serif" }}>
      <div className="pt-16" style={{ background: "linear-gradient(135deg, #064E3B, #065F46)" }}>
        <div className="max-w-7xl mx-auto px-6 py-20">
          <Link href="/services" className="inline-flex items-center gap-1.5 text-xs font-semibold mb-6 hover:opacity-70" style={{ color: "#6EE7B7" }}>← Services</Link>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
            <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
              <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-bold mb-4" style={{ background: "rgba(16,185,129,0.2)", color: "#6EE7B7" }}>
                <BookOpen size={12} /> Education, Training & Internships
              </span>
              <h1 className="text-5xl font-extrabold text-white mb-4 leading-tight" style={{ fontFamily: "'Outfit', sans-serif" }}>
                Real Projects.<br />Real Skills.<br />Real Careers.
              </h1>
              <p className="text-lg mb-8" style={{ color: "#A7F3D0" }}>
                We bridge the gap between classroom and career — giving students hands-on industry experience and giving enterprises the talent pipeline they need.
              </p>
              <Link href="/contact" className="inline-flex items-center gap-2 px-6 py-3 rounded-xl text-sm font-semibold text-white" style={{ background: "#059669" }}>
                Enroll Now <ArrowRight size={16} />
              </Link>
            </motion.div>
            <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.7, delay: 0.2 }}
              className="hidden lg:block rounded-2xl overflow-hidden shadow-2xl">
              <img src="https://images.unsplash.com/photo-1523580494863-6f3031224c94?w=700&h=500&fit=crop&auto=format"
                alt="Students working on live projects" className="w-full object-cover" style={{ aspectRatio: "7/5" }} />
            </motion.div>
          </div>
        </div>
      </div>

      <section className="py-20 bg-white">
        <div className="max-w-7xl mx-auto px-6">
          <FadeIn className="mb-12">
            <h2 className="text-3xl font-extrabold mb-3" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>Our Programme Tracks</h2>
          </FadeIn>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {[
              {
                title: "Student Internship Programme",
                icon: GraduationCap,
                desc: "Final-year and pre-final-year students from partner colleges work on live client projects — not dummy assignments. This ensures they graduate job-ready, and gives our clients a preview hire before formal onboarding.",
                points: ["6–12 week immersive internships", "Mentored by industry professionals", "Stipend-based, performance-driven", "Top performers offered full-time roles", "50+ partner colleges across India"],
              },
              {
                title: "Corporate Upskilling & L&D",
                icon: Building2,
                desc: "We design and deliver customized learning & development programmes for mid-size and large enterprises. From tech upskilling to leadership development, our workshops are outcome-driven and measurable.",
                points: ["Needs assessment before every engagement", "On-site and virtual delivery", "Data analytics, cloud, AI/ML tracks", "Leadership and communication modules", "Pre/post assessment with ROI reporting"],
              },
              {
                title: "EdTech Certification Tracks",
                icon: BadgeCheck,
                desc: "Structured 8–12 week online certification programmes covering in-demand skills. Designed in collaboration with industry partners, every track ends with a portfolio project and placement assistance.",
                points: ["Full-Stack Web Development", "Data Science & Machine Learning", "Cloud Computing (AWS/Azure)", "Product Management Fundamentals", "Placement assistance on completion"],
              },
              {
                title: "Skill Bootcamps",
                icon: Zap,
                desc: "Short-form, intensive bootcamps for professionals looking to switch roles or deepen expertise. Delivered in cohort format with peer learning and live industry challenges.",
                points: ["2–4 week intensive format", "Cohort of 20–30 learners", "Real case studies and live challenges", "Career coaching included", "Certifications from SPSTechnosoft + industry partners"],
              },
            ].map(({ title, icon: Icon, desc, points }, i) => (
              <FadeIn key={title} delay={i * 0.1}>
                <div className="rounded-2xl p-7 h-full" style={{ background: "#F0F4FA", border: "1px solid rgba(5,150,105,0.15)" }}>
                  <div className="w-12 h-12 rounded-xl flex items-center justify-center mb-4" style={{ background: "#D1FAE5" }}>
                    <Icon size={22} style={{ color: "#059669" }} />
                  </div>
                  <h3 className="text-lg font-bold mb-3" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>{title}</h3>
                  <p className="text-sm leading-relaxed mb-4" style={{ color: "#5A6B8A" }}>{desc}</p>
                  <ul className="space-y-2">
                    {points.map(p => (
                      <li key={p} className="flex items-center gap-2 text-xs" style={{ color: "#5A6B8A" }}>
                        <CheckCircle size={13} style={{ color: "#059669" }} />
                        {p}
                      </li>
                    ))}
                  </ul>
                </div>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      <section className="py-16 bg-white text-center">
        <FadeIn>
          <h2 className="text-3xl font-extrabold mb-4" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>Interested in Our Programmes?</h2>
          <div className="flex flex-wrap gap-4 justify-center">
            <Link href="/contact" className="inline-flex items-center gap-2 px-6 py-3 rounded-xl text-sm font-semibold text-white" style={{ background: "#059669" }}>
              Enquire for Internships <ArrowRight size={16} />
            </Link>
            <Link href="/contact" className="inline-flex items-center gap-2 px-6 py-3 rounded-xl text-sm font-semibold" style={{ color: "#059669", border: "2px solid #059669" }}>
              Partner as a College
            </Link>
          </div>
        </FadeIn>
      </section>
    </div>
  );
}

// ── IT SERVICES DETAIL PAGE ─────────────────────────────────────────────────
export function ITServicesPage() {
  const services = [
    { icon: Code2, title: "Custom Software Development", desc: "Scalable, maintainable web and mobile applications built with modern stacks — React, Node.js, Python, Flutter, and more.", color: "#7C3AED" },
    { icon: Cloud, title: "Cloud & DevOps Engineering", desc: "End-to-end cloud migration and managed infrastructure on AWS, Azure, and GCP, with automated CI/CD pipelines.", color: "#2563EB" },
    { icon: Brain, title: "AI & Machine Learning", desc: "Intelligent automation, predictive analytics, NLP-powered tools, and computer vision solutions for enterprise needs.", color: "#0891B2" },
    { icon: Database, title: "Data Engineering & BI", desc: "Modern data pipelines, warehouses (Snowflake, BigQuery), and interactive BI dashboards for data-driven decisions.", color: "#059669" },
    { icon: Smartphone, title: "Mobile App Development", desc: "Cross-platform iOS and Android apps with exceptional UX, built to perform at scale.", color: "#D97706" },
    { icon: Shield, title: "Security & Compliance", desc: "Application security audits, penetration testing, VAPT, and compliance readiness for GDPR, ISO 27001.", color: "#DC2626" },
    { icon: RefreshCcw, title: "Digital Transformation", desc: "Strategic advisory and execution for legacy system modernization, process automation, and tech stack evolution.", color: "#7C3AED" },
    { icon: Cpu, title: "Embedded & IoT Solutions", desc: "Hardware-software integration for smart devices, industrial IoT, and connected product ecosystems.", color: "#0891B2" },
  ];

  return (
    <div style={{ fontFamily: "'DM Sans', sans-serif" }}>
      <div className="pt-16" style={{ background: "linear-gradient(135deg, #2E1065, #4C1D95)" }}>
        <div className="max-w-7xl mx-auto px-6 py-20">
          <Link href="/services" className="inline-flex items-center gap-1.5 text-xs font-semibold mb-6 hover:opacity-70" style={{ color: "#C4B5FD" }}>← Services</Link>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
            <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
              <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-bold mb-4" style={{ background: "rgba(124,58,237,0.2)", color: "#C4B5FD" }}>
                <Monitor size={12} /> IT Services & Consulting
              </span>
              <h1 className="text-5xl font-extrabold text-white mb-4 leading-tight" style={{ fontFamily: "'Outfit', sans-serif" }}>
                Technology That<br />Drives Business.
              </h1>
              <p className="text-lg mb-8" style={{ color: "#DDD6FE" }}>
                From product build to AI integration to cloud infrastructure — SPSTechnosoft's IT consulting team engineers solutions that solve real business problems.
              </p>
              <div className="flex gap-4">
                <Link href="/contact" className="inline-flex items-center gap-2 px-6 py-3 rounded-xl text-sm font-semibold text-white" style={{ background: "#7C3AED" }}>
                  Start a Project <ArrowRight size={16} />
                </Link>
              </div>
            </motion.div>
            <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.7, delay: 0.2 }}
              className="hidden lg:block rounded-2xl overflow-hidden shadow-2xl">
              <img src="https://images.unsplash.com/photo-1518770660439-4636190af475?w=700&h=500&fit=crop&auto=format"
                alt="Technology consulting workspace" className="w-full object-cover" style={{ aspectRatio: "7/5" }} />
            </motion.div>
          </div>
        </div>
      </div>

      <section className="py-24 bg-white">
        <div className="max-w-7xl mx-auto px-6">
          <FadeIn className="mb-12">
            <h2 className="text-3xl font-extrabold mb-3" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>What We Build & Deliver</h2>
            <p className="text-sm" style={{ color: "#5A6B8A" }}>250+ projects delivered across startups and enterprises. Here's our service portfolio.</p>
          </FadeIn>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {services.map(({ icon: Icon, title, desc, color }, i) => (
              <FadeIn key={title} delay={i * 0.07}>
                <div className="rounded-2xl p-6 h-full" style={{ background: "#F0F4FA", border: "1px solid rgba(10,22,40,0.07)" }}>
                  <div className="w-11 h-11 rounded-xl flex items-center justify-center mb-4" style={{ background: `${color}15` }}>
                    <Icon size={20} style={{ color }} />
                  </div>
                  <h4 className="font-bold mb-2 text-sm" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>{title}</h4>
                  <p className="text-xs leading-relaxed" style={{ color: "#5A6B8A" }}>{desc}</p>
                </div>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      <section className="py-20" style={{ background: "#F0F4FA" }}>
        <div className="max-w-7xl mx-auto px-6 grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
          <FadeIn>
            <h2 className="text-3xl font-extrabold mb-4" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>AI at the Core of Everything We Build</h2>
            <p className="text-sm leading-relaxed mb-5" style={{ color: "#5A6B8A" }}>
              Across every engagement, our teams embed AI where it creates the most leverage — whether that's intelligent document processing, recommendation systems, anomaly detection, or AI-powered internal tools. We don't add AI as an afterthought; it's baked into our delivery approach from the discovery phase.
            </p>
            {[
              "GPT-powered internal knowledge bases and chatbots",
              "ML-based predictive analytics for operations",
              "Computer vision for quality control and inspection",
              "NLP pipelines for document automation",
              "AI-assisted code review and QA tooling",
            ].map(item => (
              <div key={item} className="flex items-center gap-3 py-2.5" style={{ borderBottom: "1px solid rgba(10,22,40,0.06)" }}>
                <Zap size={15} style={{ color: "#7C3AED" }} />
                <span className="text-sm" style={{ color: "#5A6B8A" }}>{item}</span>
              </div>
            ))}
          </FadeIn>
          <FadeIn delay={0.2}>
            <div className="rounded-2xl overflow-hidden shadow-xl">
              <img src="https://images.unsplash.com/photo-1677442135703-1787eea5ce01?w=700&h=500&fit=crop&auto=format"
                alt="AI and technology" className="w-full object-cover" style={{ aspectRatio: "7/5" }} />
            </div>
          </FadeIn>
        </div>
      </section>

      <section className="py-16 bg-white text-center">
        <FadeIn>
          <h2 className="text-3xl font-extrabold mb-4" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>Have a Project in Mind?</h2>
          <p className="text-sm mb-6" style={{ color: "#5A6B8A" }}>Share your brief and our consulting team will respond with a discovery call within 48 hours.</p>
          <Link href="/contact" className="inline-flex items-center gap-2 px-7 py-3.5 rounded-xl text-sm font-semibold text-white" style={{ background: "#7C3AED" }}>
            Request a Consultation <ArrowRight size={16} />
          </Link>
        </FadeIn>
      </section>
    </div>
  );
}

// ── ABOUT PAGE ──────────────────────────────────────────────────────────────
export function AboutPage() {
  const directors = [
    {
      name: "Rajan Krishnamurthy",
      role: "Founder & CEO",
      image: "https://images.unsplash.com/photo-1560250097-0b93528c311a?w=400&h=400&fit=crop&auto=format",
      bio: "With 18 years across talent management and organizational consulting, Rajan founded SPSTechnosoft to build the kind of hiring partner he wished had existed during his corporate career. He's passionate about creating structures that let people and organizations do their best work.",
      linkedin: "#",
    },
    {
      name: "Deepa Anand",
      role: "Co-Founder & COO",
      image: "https://images.unsplash.com/photo-1573496799652-408c2ac9fe98?w=400&h=400&fit=crop&auto=format",
      bio: "Deepa brings operational rigor and a sharp eye for culture-fit to SPSTechnosoft's day-to-day. Before co-founding SPSTechnosoft, she led talent acquisition at two unicorn startups. She oversees SPSTechnosoft's delivery quality, client relationships, and EdTech vertical.",
      linkedin: "#",
    },
    {
      name: "Aryan Shah",
      role: "CTO & Head of IT Consulting",
      image: "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=400&h=400&fit=crop&auto=format",
      bio: "Aryan leads SPSTechnosoft's technology vertical and internal engineering. A full-stack architect with experience at top product companies, he built SPSTechnosoft's proprietary candidate screening platform and is the driving force behind the company's AI-first internal systems.",
      linkedin: "#",
    },
  ];

  return (
    <div style={{ fontFamily: "'DM Sans', sans-serif" }}>
      <div className="pt-16" style={{ background: "linear-gradient(135deg, #0A1628, #1A2F6B)" }}>
        <div className="max-w-7xl mx-auto px-6 py-20 text-center">
          <motion.h1 initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}
            className="text-5xl font-extrabold text-white mb-4" style={{ fontFamily: "'Outfit', sans-serif" }}>
            The People Behind SPSTechnosoft
          </motion.h1>
          <motion.p initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.2 }}
            className="text-lg max-w-2xl mx-auto" style={{ color: "#8FA3C0" }}>
            SPSTechnosoft was built by practitioners — people who have worked in the same roles, industries, and pressures as our clients. That empathy is our competitive advantage.
          </motion.p>
        </div>
      </div>

      {/* Directors */}
      <section className="py-24 bg-white">
        <div className="max-w-7xl mx-auto px-6">
          <FadeIn className="mb-12">
            <span className="inline-block text-xs font-bold uppercase tracking-widest mb-3 px-3 py-1 rounded-full" style={{ background: "#E8EFFE", color: "#1A56DB" }}>Leadership</span>
            <h2 className="text-3xl font-extrabold" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>Our Directors</h2>
          </FadeIn>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {directors.map(({ name, role, image, bio, linkedin }, i) => (
              <FadeIn key={name} delay={i * 0.15}>
                <div className="rounded-2xl overflow-hidden shadow-md" style={{ border: "1px solid rgba(10,22,40,0.08)" }}>
                  <div className="h-56 overflow-hidden">
                    <img src={image} alt={name} className="w-full h-full object-cover object-top" />
                  </div>
                  <div className="p-6">
                    <h3 className="text-lg font-bold" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>{name}</h3>
                    <p className="text-xs font-semibold mb-3" style={{ color: "#1A56DB" }}>{role}</p>
                    <p className="text-sm leading-relaxed mb-4" style={{ color: "#5A6B8A" }}>{bio}</p>
                    <a href={linkedin} className="inline-flex items-center gap-2 text-xs font-semibold transition-colors hover:opacity-70" style={{ color: "#0A1628" }}>
                      <Linkedin size={14} /> Connect on LinkedIn
                    </a>
                  </div>
                </div>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      {/* Startups & Enterprise */}
      <section className="py-24" style={{ background: "#F0F4FA" }}>
        <div className="max-w-7xl mx-auto px-6">
          <FadeIn className="text-center mb-14">
            <span className="inline-block text-xs font-bold uppercase tracking-widest mb-3 px-3 py-1 rounded-full" style={{ background: "#E8EFFE", color: "#1A56DB" }}>Who We Serve</span>
            <h2 className="text-4xl font-extrabold mb-4" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>Built for Startups and Enterprises Alike</h2>
            <p className="text-base max-w-xl mx-auto" style={{ color: "#5A6B8A" }}>Two very different speeds. One consistent standard of delivery.</p>
          </FadeIn>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {[
              {
                icon: Rocket,
                type: "Startups",
                color: "#1A56DB",
                bg: "#E8EFFE",
                headline: "Scale from 5 to 50 — without chaos.",
                desc: "Startups need to move fast, but poor hires at early stages are expensive mistakes. SPSTechnosoft acts as your outsourced talent function — sourcing, screening, and closing candidates while you stay focused on product and growth.",
                benefits: [
                  "No monthly retainer — pay per placement",
                  "Priority database access for niche roles",
                  "Fractional HR support on-demand",
                  "Internship pipeline from top colleges",
                  "IT build partners who understand product constraints",
                ],
              },
              {
                icon: Building2,
                type: "Enterprises",
                color: "#7C3AED",
                bg: "#EDE9FE",
                headline: "Standardize, scale, and transform.",
                desc: "Large organizations deal with volume hiring, skills gaps, and technology debt simultaneously. SPSTechnosoft provides structured programmes across all three verticals — delivered at enterprise scale with dedicated account management.",
                benefits: [
                  "Bulk hiring frameworks for 50+ roles/year",
                  "Custom L&D programmes for 200+ person teams",
                  "Dedicated technology pods for digital transformation",
                  "SLA-driven delivery with monthly reporting",
                  "Strategic advisory relationships with senior leadership",
                ],
              },
            ].map(({ icon: Icon, type, color, bg, headline, desc, benefits }) => (
              <FadeIn key={type}>
                <div className="rounded-2xl p-8 h-full" style={{ background: "white", border: `2px solid ${color}20` }}>
                  <div className="w-12 h-12 rounded-xl flex items-center justify-center mb-5" style={{ background: bg }}>
                    <Icon size={22} style={{ color }} />
                  </div>
                  <div className="inline-block px-3 py-1 rounded-full text-xs font-bold mb-3" style={{ background: bg, color }}>For {type}</div>
                  <h3 className="text-xl font-bold mb-3" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>{headline}</h3>
                  <p className="text-sm leading-relaxed mb-5" style={{ color: "#5A6B8A" }}>{desc}</p>
                  <ul className="space-y-2.5">
                    {benefits.map(b => (
                      <li key={b} className="flex items-start gap-3">
                        <CheckCircle size={15} className="mt-0.5 shrink-0" style={{ color }} />
                        <span className="text-sm" style={{ color: "#5A6B8A" }}>{b}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      {/* AI Adoption */}
      <section className="py-24" style={{ background: "linear-gradient(135deg, #0A1628, #0F2050)" }}>
        <div className="max-w-7xl mx-auto px-6 grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
          <FadeIn>
            <span className="inline-block text-xs font-bold uppercase tracking-widest mb-4 px-3 py-1 rounded-full" style={{ background: "rgba(26,86,219,0.2)", color: "#93BBFF" }}>AI-First Operations</span>
            <h2 className="text-4xl font-extrabold text-white mb-5" style={{ fontFamily: "'Outfit', sans-serif" }}>
              How We Use AI to Deliver Better Outcomes
            </h2>
            <p className="text-base mb-8" style={{ color: "#8FA3C0" }}>
              AI isn't a buzzword at SPSTechnosoft — it's infrastructure. We've embedded machine learning and language models across our candidate screening, client matching, and internal operations to deliver faster, more accurate results.
            </p>
            <div className="space-y-5">
              {[
                { icon: Brain, title: "AI-Powered Candidate Screening", desc: "Our proprietary screening platform uses LLMs to evaluate candidate submissions, rank suitability against JDs, and flag skill gaps — before a human recruiter even sees a profile." },
                { icon: Target, title: "Smart Job-Candidate Matching", desc: "Vector-based matching algorithms surface the best-fit profiles from our database within minutes of a new mandate being created." },
                { icon: BarChart3, title: "Predictive Placement Analytics", desc: "We analyze historic placement data to predict offer acceptance likelihood and time-to-fill for new mandates, helping clients plan more accurately." },
              ].map(({ icon: Icon, title, desc }) => (
                <div key={title} className="flex items-start gap-4 p-4 rounded-xl" style={{ background: "rgba(255,255,255,0.05)" }}>
                  <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0" style={{ background: "rgba(26,86,219,0.3)" }}>
                    <Icon size={18} style={{ color: "#93BBFF" }} />
                  </div>
                  <div>
                    <p className="text-sm font-bold text-white mb-1" style={{ fontFamily: "'Outfit', sans-serif" }}>{title}</p>
                    <p className="text-xs leading-relaxed" style={{ color: "#8FA3C0" }}>{desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </FadeIn>
          <FadeIn delay={0.2} className="hidden lg:block">
            <div className="rounded-2xl overflow-hidden shadow-2xl">
              <img src="https://images.unsplash.com/photo-1677442135703-1787eea5ce01?w=700&h=600&fit=crop&auto=format"
                alt="AI systems visualization" className="w-full object-cover" style={{ aspectRatio: "7/6" }} />
            </div>
          </FadeIn>
        </div>
      </section>
    </div>
  );
}

// ── CAREER PAGE ─────────────────────────────────────────────────────────────
export function CareerPage() {
  const [filter, setFilter] = useState("All");
  const filters = ["All", "Remote", "Contract", "Permanent"];

  const jobs = [
    { id: 1, title: "Senior React Developer", company: "FinTech Startup – Mumbai", type: "Remote", salary: "₹25–35 LPA", skills: ["React", "TypeScript", "Node.js"], posted: "2 days ago", urgent: true },
    { id: 2, title: "Data Scientist – NLP", company: "AI Product Company – Bengaluru", type: "Permanent", salary: "₹30–45 LPA", skills: ["Python", "NLP", "PyTorch"], posted: "4 days ago", urgent: false },
    { id: 3, title: "DevOps Engineer", company: "E-Commerce Platform – Delhi", type: "Contract", salary: "₹8,000/day", skills: ["Kubernetes", "Terraform", "AWS"], posted: "1 day ago", urgent: true },
    { id: 4, title: "Product Manager – B2B SaaS", company: "Enterprise SaaS – Pune", type: "Permanent", salary: "₹28–38 LPA", skills: ["Product Strategy", "SQL", "Stakeholder Mgmt"], posted: "6 days ago", urgent: false },
    { id: 5, title: "Cloud Architect", company: "Logistics Tech – Hyderabad", type: "Contract", salary: "₹10,000/day", skills: ["AWS", "Microservices", "Solution Design"], posted: "Today", urgent: true },
    { id: 6, title: "UX Designer – Mobile", company: "Consumer App – Remote", type: "Remote", salary: "₹18–25 LPA", skills: ["Figma", "User Research", "Prototyping"], posted: "3 days ago", urgent: false },
  ];

  const filtered = filter === "All" ? jobs : jobs.filter(j => j.type === filter);

  const steps = [
    { step: "01", icon: Search, title: "Apply for the Role", desc: "Submit your application via the job listing. Our AI immediately parses your resume and matches your profile to the role requirements." },
    { step: "02", icon: Brain, title: "AI-Monitored Assessment", desc: "Receive a link to a role-specific assessment monitored by our AI proctoring system. Tests cover technical aptitude and domain knowledge." },
    { step: "03", icon: Video, title: "3 Interview Rounds", desc: "Technical screening, domain panel review, and a cross-functional round with stakeholders from the client team." },
    { step: "04", icon: Users, title: "Managerial Round", desc: "A conversation with the hiring manager or team lead to align on expectations, working style, and growth trajectory." },
    { step: "05", icon: MessageSquare, title: "HR Discussion", desc: "Compensation structure, joining timelines, benefits, and any remaining questions handled transparently." },
    { step: "06", icon: BadgeCheck, title: "Offer Letter", desc: "Formal offer issued and negotiated with our support. We stay involved until your Day 1 is confirmed." },
  ];

  const candidateReviews = [
    { quote: "The entire process was transparent and fast. From applying to receiving my offer took 18 days. SPSTechnosoft kept me informed at every step.", name: "Kabir Mehta", role: "Placed as Senior Backend Engineer", avatar: "KM" },
    { quote: "The AI assessment was the most thoughtful screening I've encountered — it was actually designed for the role, not a generic test. Impressed.", name: "Anjali Desai", role: "Placed as Data Scientist", avatar: "AD" },
    { quote: "As a final-year student, I was nervous about getting real industry experience. SPSTechnosoft's internship programme changed everything — I shipped production code on Week 2.", name: "Rohan Iyer", role: "Intern → Full-time at NovaBuild", avatar: "RI" },
  ];

  const typeColor = (type: string) => {
    if (type === "Remote") return { bg: "#DCFCE7", color: "#15803D" };
    if (type === "Contract") return { bg: "#FEF3C7", color: "#D97706" };
    return { bg: "#E8EFFE", color: "#1A56DB" };
  };

  return (
    <div style={{ fontFamily: "'DM Sans', sans-serif" }}>
      <div className="pt-16" style={{ background: "linear-gradient(135deg, #0A1628, #0D2150)" }}>
        <div className="max-w-7xl mx-auto px-6 py-20 text-center">
          <motion.h1 initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}
            className="text-5xl font-extrabold text-white mb-4" style={{ fontFamily: "'Outfit', sans-serif" }}>
            Your Next Role Starts Here
          </motion.h1>
          <motion.p initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.2 }}
            className="text-lg max-w-2xl mx-auto mb-6" style={{ color: "#8FA3C0" }}>
            We hire for remote, contract, and permanent roles across technology, finance, and operations. And if you're a student, our internship programme gives you real industry experience on live projects.
          </motion.p>
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.3 }}
            className="flex flex-wrap gap-3 justify-center">
            {filters.map(f => (
              <button key={f} onClick={() => setFilter(f)}
                className="px-5 py-2 rounded-xl text-sm font-semibold transition-all duration-200"
                style={filter === f ? { background: "#1A56DB", color: "white" } : { background: "rgba(255,255,255,0.1)", color: "#93BBFF" }}>
                {f}
              </button>
            ))}
          </motion.div>
        </div>
      </div>

      {/* Job Listings */}
      <section className="py-20 bg-white">
        <div className="max-w-7xl mx-auto px-6">
          <FadeIn className="flex items-center justify-between mb-8">
            <h2 className="text-2xl font-bold" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>
              Open Positions <span className="text-lg font-normal ml-2" style={{ color: "#5A6B8A" }}>({filtered.length} roles)</span>
            </h2>
          </FadeIn>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {filtered.map((job, i) => {
              const { bg, color } = typeColor(job.type);
              return (
                <FadeIn key={job.id} delay={i * 0.08}>
                  <div className="rounded-2xl p-6 flex flex-col gap-4 hover:shadow-md transition-all duration-200 cursor-pointer group"
                    style={{ border: "1px solid rgba(10,22,40,0.1)", background: "white" }}>
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          {job.urgent && (
                            <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded-full" style={{ background: "#FEE2E2", color: "#DC2626" }}>Urgent</span>
                          )}
                          <span className="text-xs font-semibold px-2 py-0.5 rounded-full" style={{ background: bg, color }}>{job.type}</span>
                        </div>
                        <h3 className="text-base font-bold group-hover:text-[#1A56DB] transition-colors" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>{job.title}</h3>
                        <p className="text-xs mt-0.5" style={{ color: "#5A6B8A" }}>{job.company}</p>
                      </div>
                      <ArrowUpRight size={18} className="shrink-0 group-hover:text-[#1A56DB] transition-colors" style={{ color: "#DDE4F0", marginTop: "4px" }} />
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {job.skills.map(s => (
                        <span key={s} className="px-2.5 py-1 rounded-lg text-xs font-medium" style={{ background: "#F0F4FA", color: "#5A6B8A" }}>{s}</span>
                      ))}
                    </div>
                    <div className="flex items-center justify-between pt-2" style={{ borderTop: "1px solid rgba(10,22,40,0.06)" }}>
                      <span className="text-sm font-bold" style={{ color: "#0A1628" }}>{job.salary}</span>
                      <span className="text-xs" style={{ color: "#5A6B8A" }}>Posted {job.posted}</span>
                    </div>
                  </div>
                </FadeIn>
              );
            })}
          </div>
          <FadeIn className="text-center mt-10">
            <Link href="/contact" className="inline-flex items-center gap-2 px-6 py-3 rounded-xl text-sm font-semibold text-white" style={{ background: "#1A56DB" }}>
              Submit Your Resume <ArrowRight size={16} />
            </Link>
          </FadeIn>
        </div>
      </section>

      {/* Hiring Process */}
      <section className="py-24" style={{ background: "#F0F4FA" }}>
        <div className="max-w-7xl mx-auto px-6">
          <FadeIn className="text-center mb-14">
            <span className="inline-block text-xs font-bold uppercase tracking-widest mb-3 px-3 py-1 rounded-full" style={{ background: "#E8EFFE", color: "#1A56DB" }}>Our Process</span>
            <h2 className="text-4xl font-extrabold mb-3" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>How We Hire</h2>
            <p className="text-sm max-w-xl mx-auto" style={{ color: "#5A6B8A" }}>A structured, six-stage process designed to be fair, transparent, and fast — for both candidates and clients.</p>
          </FadeIn>
          <div className="relative">
            <div className="hidden lg:block absolute top-8 left-[8%] right-[8%] h-0.5" style={{ background: "linear-gradient(to right, #E8EFFE, #1A56DB, #E8EFFE)" }} />
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-6">
              {steps.map(({ step, icon: Icon, title, desc }, i) => (
                <FadeIn key={step} delay={i * 0.1}>
                  <div className="flex flex-col items-center text-center">
                    <div className="w-16 h-16 rounded-full flex items-center justify-center mb-4 relative z-10 shadow-lg"
                      style={{ background: i < 3 ? "linear-gradient(135deg, #0A1628, #1A56DB)" : "white", border: "3px solid #E8EFFE" }}>
                      <Icon size={20} style={{ color: i < 3 ? "white" : "#1A56DB" }} />
                    </div>
                    <span className="text-xs font-bold mb-1" style={{ color: "#1A56DB" }}>{step}</span>
                    <h4 className="text-sm font-bold mb-2" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>{title}</h4>
                    <p className="text-xs leading-relaxed" style={{ color: "#5A6B8A" }}>{desc}</p>
                  </div>
                </FadeIn>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Candidate Reviews */}
      <section className="py-24 bg-white">
        <div className="max-w-7xl mx-auto px-6">
          <FadeIn className="text-center mb-12">
            <h2 className="text-3xl font-extrabold" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>What Candidates Say</h2>
          </FadeIn>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {candidateReviews.map(({ quote, name, role, avatar }, i) => (
              <FadeIn key={name} delay={i * 0.15}>
                <div className="rounded-2xl p-7 flex flex-col gap-4 h-full" style={{ background: "#F0F4FA", border: "1px solid rgba(10,22,40,0.07)" }}>
                  <Quote size={24} style={{ color: "#DDE4F0" }} />
                  <p className="text-sm leading-relaxed flex-1" style={{ color: "#5A6B8A" }}>{quote}</p>
                  <div className="flex items-center gap-3 pt-3" style={{ borderTop: "1px solid rgba(10,22,40,0.07)" }}>
                    <div className="w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold text-white shrink-0"
                      style={{ background: "linear-gradient(135deg, #0A1628, #1A56DB)" }}>{avatar}</div>
                    <div>
                      <p className="text-sm font-bold" style={{ color: "#0A1628" }}>{name}</p>
                      <p className="text-xs" style={{ color: "#5A6B8A" }}>{role}</p>
                    </div>
                  </div>
                </div>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      {/* Internship CTA */}
      <section className="py-16" style={{ background: "linear-gradient(135deg, #064E3B, #065F46)" }}>
        <FadeIn className="max-w-3xl mx-auto px-6 text-center">
          <GraduationCap size={40} className="mx-auto mb-4" style={{ color: "#6EE7B7" }} />
          <h2 className="text-3xl font-extrabold text-white mb-3" style={{ fontFamily: "'Outfit', sans-serif" }}>Are You a College Student?</h2>
          <p className="text-base mb-6" style={{ color: "#A7F3D0" }}>
            Our internship programme places you on live organizational projects — not dummy assignments. Build a real portfolio, get mentored by industry professionals, and land your first job through our campus-to-corporate pipeline.
          </p>
          <Link href="/contact" className="inline-flex items-center gap-2 px-7 py-3.5 rounded-xl text-sm font-semibold text-white hover:opacity-90 transition-all"
            style={{ background: "#059669" }}>
            Apply for an Internship <ArrowRight size={16} />
          </Link>
        </FadeIn>
      </section>
    </div>
  );
}

// ── CONTACT PAGE ────────────────────────────────────────────────────────────
export function ContactPage() {
  const [form, setForm] = useState({ name: "", email: "", phone: "", subject: "", message: "" });
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitted(true);
  };

  return (
    <div style={{ fontFamily: "'DM Sans', sans-serif" }}>
      <div className="pt-16" style={{ background: "linear-gradient(135deg, #0A1628, #0D2150)" }}>
        <div className="max-w-7xl mx-auto px-6 py-20 text-center">
          <motion.h1 initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}
            className="text-5xl font-extrabold text-white mb-4" style={{ fontFamily: "'Outfit', sans-serif" }}>
            Let's Talk
          </motion.h1>
          <motion.p initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.2 }}
            className="text-lg max-w-xl mx-auto" style={{ color: "#8FA3C0" }}>
            Whether you want to hire, learn, or build — we'd love to hear from you. Fill out the form or reach us directly.
          </motion.p>
        </div>
      </div>

      <section className="py-24" style={{ background: "#F0F4FA" }}>
        <div className="max-w-7xl mx-auto px-6 grid grid-cols-1 lg:grid-cols-3 gap-12">

          {/* Info */}
          <FadeIn className="space-y-6">
            <div>
              <h3 className="text-xl font-bold mb-4" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>Reach Us Directly</h3>
              {[
                { icon: Mail, label: "Email", value: "hello@stratumgroup.in", sub: "Replies within 4 business hours" },
                { icon: Phone, label: "Phone", value: "+91 98765 43210", sub: "Mon–Sat, 9 AM – 7 PM IST" },
                { icon: MapPin, label: "Office", value: "Koramangala, Bengaluru", sub: "Karnataka, India – 560034" },
              ].map(({ icon: Icon, label, value, sub }) => (
                <div key={label} className="flex items-start gap-4 p-4 rounded-xl bg-white shadow-sm mb-3" style={{ border: "1px solid rgba(10,22,40,0.08)" }}>
                  <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0" style={{ background: "#E8EFFE" }}>
                    <Icon size={18} style={{ color: "#1A56DB" }} />
                  </div>
                  <div>
                    <p className="text-xs font-bold uppercase tracking-wider mb-0.5" style={{ color: "#5A6B8A" }}>{label}</p>
                    <p className="text-sm font-semibold" style={{ color: "#0A1628" }}>{value}</p>
                    <p className="text-xs" style={{ color: "#5A6B8A" }}>{sub}</p>
                  </div>
                </div>
              ))}
            </div>

            <div className="p-5 rounded-2xl" style={{ background: "#0A1628" }}>
              <h4 className="font-bold text-white text-sm mb-3" style={{ fontFamily: "'Outfit', sans-serif" }}>Quick Topics</h4>
              {["I want to hire talent", "I'm a candidate looking for a role", "I need IT consulting", "Corporate training enquiry", "Internship programme"].map(t => (
                <div key={t} className="flex items-center gap-2 py-2" style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
                  <ChevronRight size={13} style={{ color: "#1A56DB" }} />
                  <span className="text-xs" style={{ color: "#8FA3C0" }}>{t}</span>
                </div>
              ))}
            </div>
          </FadeIn>

          {/* Form */}
          <FadeIn delay={0.15} className="lg:col-span-2">
            <div className="bg-white rounded-2xl p-8 shadow-md" style={{ border: "1px solid rgba(10,22,40,0.08)" }}>
              {submitted ? (
                <div className="text-center py-16">
                  <div className="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4" style={{ background: "#D1FAE5" }}>
                    <CheckCircle size={32} style={{ color: "#059669" }} />
                  </div>
                  <h3 className="text-2xl font-bold mb-2" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>Message Received!</h3>
                  <p className="text-sm" style={{ color: "#5A6B8A" }}>Our team will get back to you within 4 business hours. Watch your inbox.</p>
                  <button onClick={() => setSubmitted(false)} className="mt-6 text-sm font-semibold" style={{ color: "#1A56DB" }}>Send another message</button>
                </div>
              ) : (
                <>
                  <h3 className="text-xl font-bold mb-6" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>Send Us a Message</h3>
                  <form onSubmit={handleSubmit} className="space-y-5">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                      {[
                        { key: "name", label: "Full Name", placeholder: "Priya Sharma", type: "text" },
                        { key: "email", label: "Email Address", placeholder: "priya@company.com", type: "email" },
                        { key: "phone", label: "Phone Number", placeholder: "+91 98765 43210", type: "tel" },
                        { key: "subject", label: "Subject", placeholder: "How can we help?", type: "text" },
                      ].map(({ key, label, placeholder, type }) => (
                        <div key={key}>
                          <label className="block text-xs font-semibold mb-1.5 uppercase tracking-wider" style={{ color: "#5A6B8A" }}>{label}</label>
                          <input
                            type={type}
                            placeholder={placeholder}
                            required
                            value={form[key as keyof typeof form]}
                            onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
                            className="w-full px-4 py-3 rounded-xl text-sm outline-none focus:ring-2 focus:ring-[#1A56DB]/30 transition-all"
                            style={{ background: "#F0F4FA", border: "1px solid rgba(10,22,40,0.1)", color: "#0A1628" }}
                          />
                        </div>
                      ))}
                    </div>
                    <div>
                      <label className="block text-xs font-semibold mb-1.5 uppercase tracking-wider" style={{ color: "#5A6B8A" }}>Message</label>
                      <textarea
                        rows={5}
                        placeholder="Tell us about your requirement — the more detail, the faster we can help..."
                        required
                        value={form.message}
                        onChange={e => setForm(f => ({ ...f, message: e.target.value }))}
                        className="w-full px-4 py-3 rounded-xl text-sm outline-none focus:ring-2 focus:ring-[#1A56DB]/30 transition-all resize-none"
                        style={{ background: "#F0F4FA", border: "1px solid rgba(10,22,40,0.1)", color: "#0A1628" }}
                      />
                    </div>
                    <button type="submit"
                      className="w-full flex items-center justify-center gap-2 py-3.5 rounded-xl text-sm font-semibold text-white transition-all hover:opacity-90 hover:shadow-lg"
                      style={{ background: "linear-gradient(135deg, #0A1628, #1A56DB)" }}>
                      <Send size={16} />
                      Send Message
                    </button>
                  </form>
                </>
              )}
            </div>
          </FadeIn>
        </div>
      </section>
    </div>
  );
}
