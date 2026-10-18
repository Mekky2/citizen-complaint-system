# Administrator / Authority Reviewer - User Stories

> Each story has an ID that is referenced from the [implementation plan](./implementation_plan.md).

This document outlines all Agile user stories for the combined Administrator and Authority Reviewer persona. This role is responsible for overseeing the dashboard, managing the ticket lifecycle, and validating completed work.

## Super Administrator (System Management)

* <a id="sup-01"></a>**[SUP-01] As a Super Administrator**, I want to create, edit, and manage accounts for other Administrators and Authority Reviewers so that I can onboard new municipal staff to the system.

* <a id="sup-02"></a>**[SUP-02] As a Super Administrator**, I want to create and manage accounts for Maintenance Teams so that they can access the platform to receive tasks and upload proof of work.

* <a id="sup-03"></a>**[SUP-03] As a Super Administrator**, I want to assign specific department roles (e.g., Water, Roads, Electricity) to Admin accounts so that they only have access to the dashboard and complaints relevant to their specific authority.

## Dashboard, Notifications & AI Insights

* <a id="adm-01"></a>**[ADM-01] As an Administrator/Reviewer**, I want to access a centralized government dashboard so that I can view all incoming complaints assigned to my specific department.

* <a id="adm-02"></a>**[ADM-02] As an Administrator/Reviewer**, I want to receive in-app dashboard notifications (new ticket in my department, ticket moved to Verifying) so that I can act on time without refreshing the page.

* <a id="adm-03"></a>**[ADM-03] As an Administrator/Reviewer**, I want to see the AI-generated severity level (e.g., Critical, Medium, Weak) for each new ticket so that I can immediately prioritize urgent public safety hazards over routine issues.

* <a id="adm-04"></a>**[ADM-04] As an Administrator/Reviewer**, I want tickets where the AI could not finish analysis to be clearly flagged "Needs manual review" so that I can classify and handle them myself.

* <a id="adm-05"></a>**[ADM-05] As an Administrator/Reviewer**, I want to view the AI-generated, policy-aligned recommendations and retrieved RAG context so that I can make informed decisions based on official government laws and regulations.

## Triage & Assignment (Human-in-the-Loop)

* <a id="adm-06"></a>**[ADM-06] As an Administrator/Reviewer**, I want the ability to review the full details of a complaint (description, photos, location, citizen info) so that I understand the full context of the reported problem.

* <a id="adm-07"></a>**[ADM-07] As an Administrator/Reviewer**, I want to approve legitimate complaints or dismiss invalid/duplicate ones so that municipal resources are only allocated to real issues.

* <a id="adm-08"></a>**[ADM-08] As an Administrator/Reviewer**, I want to assign an approved ticket to a specific maintenance team, which moves the ticket to In Progress, so that the right personnel are dispatched to resolve the problem.

## Tracking & Verification

* <a id="adm-09"></a>**[ADM-09] As an Administrator/Reviewer**, I want to track the real-time status of all tickets (Pending → Approved → In Progress → Verifying → Done, including tickets returned to In Progress after rejected proof) so that I have complete visibility over the department's active operations.

* <a id="adm-10"></a>**[ADM-10] As an Administrator/Reviewer**, I want a "Verifying" queue of tickets whose work the maintenance team has marked completed so that I can review them efficiently.

* <a id="adm-11"></a>**[ADM-11] As an Administrator/Reviewer**, I want to review the photographic evidence and completion reports uploaded by the maintenance team so that I can visually verify that the repair was executed properly.

* <a id="adm-12"></a>**[ADM-12] As an Administrator/Reviewer**, I want to officially confirm the proof of work and mark the ticket as "Done" so that the case is formally closed and accountable.

* <a id="adm-13"></a>**[ADM-13] As an Administrator/Reviewer**, I want to reject insufficient proof of work with a short note, which returns the ticket to In Progress, so that the maintenance team redoes or re-documents the work before the case is closed.

* <a id="adm-14"></a>**[ADM-14] As an Administrator/Reviewer**, I want to be able to both assign a ticket's work and verify its completion so that one accountable owner manages the ticket end to end.

## Analytics & Reporting

* <a id="adm-15"></a>**[ADM-15] As an Administrator/Reviewer**, I want to view auto-generated graphs, numbers, and reports from the embedded Analytics AI so that I can track department efficiency, identify recurring municipal problems, and make data-driven infrastructure decisions.
