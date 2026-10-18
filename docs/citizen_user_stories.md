# Citizen (End User) - User Stories

> Each story has an ID that is referenced from the [implementation plan](./implementation_plan.md).

This document outlines all Agile user stories specifically focused on the Citizen's interactions with the Complaint Management System.

## Submission & Data Entry

* <a id="cit-01"></a>**[CIT-01] As a citizen**, I want to submit a complaint through an accessible web form so that I can report local issues without visiting a government office.

* <a id="cit-02"></a>**[CIT-02] As a citizen**, I want to describe my issue in a free-text field so that I can provide specific context and details about the problem.

* <a id="cit-03"></a>**[CIT-03] As a citizen**, I want to select the relevant government authority (e.g., Water, Electricity, Roads) from a dropdown list so that my complaint is routed directly to the correct department.

* <a id="cit-04"></a>**[CIT-04] As a citizen**, I want to provide the exact location of the issue (e.g., using GPS coordinates or dropping a map pin) so that maintenance teams know exactly where to go.

* <a id="cit-05"></a>**[CIT-05] As a citizen**, I want to submit my personal identification details (Name, National ID) securely so that my complaint is officially recorded and verified.

* <a id="cit-06"></a>**[CIT-06] As a citizen**, I want to attach photos of the issue to my complaint so that the authority can see the problem and assess it faster.

## Validation & Feedback

* <a id="cit-07"></a>**[CIT-07] As a citizen**, I want the system to alert me if I leave any required fields blank (description, authority, location, name, National ID) so that I can ensure my complaint has all the necessary information to be processed. Photos are optional.

* <a id="cit-08"></a>**[CIT-08] As a citizen**, I want to receive a unique Ticket ID (e.g., "C123") upon submission so that I have a reference number for my reported issue.

* <a id="cit-09"></a>**[CIT-09] As a citizen**, I want to be told with a clear reason if my complaint is declined at validation (e.g., it does not match the selected authority) so that I can correct it and resubmit.

## Tracking

* <a id="cit-10"></a>**[CIT-10] As a citizen**, I want to enter my Ticket ID in the portal's tracking page so that I can see the current status of my complaint (Declined, Pending, Approved, In Progress, Verifying, Done, or Dismissed). If proof of work is rejected, the status returns to In Progress.

> Note: Citizens do not receive in-app notifications. In-app notifications exist only on the government dashboard.
