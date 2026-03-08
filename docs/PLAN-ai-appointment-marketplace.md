# PLAN: AI Appointment Marketplace (V3.0)

## Overview
This plan outlines the evolution of AI Sched into a full-scale, AI-powered two-sided marketplace connecting verified businesses with customers.

---

## 1. Architectural Decisions (Socratic Optimal)

- **Payment Engine**: **Stripe Connect (Express)**. Direct-to-Business flow with automatic platform fee deduction.
- **Waitlist Logic**: **Fair Priority (FIFO)**. Notifications sent to waitlisted users based on time joined when a slot opens.
- **AI Automation Policy**: **Human-in-the-Loop**. AI identifies delays and suggests shifts; Business Owners confirm before notifications are blasted.
- **Identity Strategy**: **Hybrid Firebase-SQL**. Firebase handles the 2FA identity; PostgreSQL handles the marketplace role-based logic and history.
- **Global Readiness**: **Timezone-aware (UTC)** database standard with local offsets in the UI.

---

## 2. Phase-by-Phase Roadmap

### Phase 1: Core Infrastructure (Infrastructure Zero)
- [ ] Migrate PostgreSQL to production-grade RDS/Supabase.
- [ ] Implement Stripe Connect onboarding for businesses.
- [ ] Add `Timezone` and `Currency` support to User/Business models.

### Phase 2: AI Scheduling Engine (The Brain)
- [ ] Smart Slot Logic: Weights availability, staff skills, and historical duration.
- [ ] Delay Prediction: Real-time conflict detection using historical 'drift'.
- [ ] Smart Waitlist: Automated SMS/Push trigger when cancellations occur.

### Phase 3: Marketplace Discovery (Elite UI)
- [ ] Global Search: Distance-based indexing for nearby appointments in <60 mins.
- [ ] 3D Spatial Map: Dynamic Three.js visualization of local businesses.
- [ ] Review Engine: AI Fraud Detection for fake/spam reviews.

### Phase 4: Business Management (Power-ups)
- [ ] Multi-branch Dashboard: Unified control for parent brands.
- [ ] Performance Insights: Peak hour heatmaps and revenue forecasting.
- [ ] Subscription Gating: Automated feature locking based on Fee/Pro/Premium.

---

## 3. Technology Stack

- **Frontend**: React / Next.js (App Router)
- **Backend**: Flask (Enterprise Patterns)
- **Identity**: Firebase Authentication
- **Payments**: Stripe Connect, Razorpay, UPI
- **AI**: Python (Scikit-learn, Gemini API for insights)
- **Real-time**: Azure Web PubSub
- **Ops**: Twilio, SendGrid

---

## 4. Verification Strategy

- **Load Testing**: Simulating 100 concurrent bookings with AI conflict detection.
- **Security Audit**: Pentesting the Stripe Connect escrow/fee flow.
- **UX Audit**: 100% Core Web Vitals and W3C Accessibility compliance.
