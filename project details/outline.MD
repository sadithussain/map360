Collaborative 3D World Mapping Platform — Project Outline
1. Vision
A social, collaborative mapping platform where users progressively build a shared 3D world by scanning real-world storefronts and landmarks. Each group maintains its own isolated version of the world map, evolving in real time as members contribute.

2. Core Concept
Start with a blank, grey 3D world map
Users join private groups
Each group has its own independent “world state”
Users contribute real-world scans of locations
The system converts these inputs into 3D models placed on the map

3. User Structure
3.1 Groups (Like Life360 circles)
Users can create or join groups
Each group has:
Its own map instance
Its own contributed content
Controlled visibility (group-only)
3.2 Permissions
Group members can:
Add new locations
View all existing mapped locations in their group
Non-members:
Cannot see group maps or content

4. Core User Flow
4.1 Exploring the Map
User opens the app
Sees a minimal grey world map
Can zoom, pan, and navigate

4.2 Adding a New Location (Contribution Flow)
Step 1: Select Location
User pins a real-world storefront/location on the map
Step 2: Capture Data
User provides one of:
Option A: 3 images
Left angle
Center angle
Right angle
 OR
Option B: ~5 second video scan
Horizontal sweep of storefront (left → right or right → left)
Step 3: Upload Submission
Media is uploaded to the system
Associated with:
GPS/location data
Group ID
User ID

4.3 Processing Pipeline (Conceptual)
System receives media
Extracts spatial and visual information
Generates a 3D mesh/model of the storefront
Aligns model to correct geolocation on map

4.4 Map Update
Newly generated 3D object is:
Added to that group’s world map
Immediately visible to all group members
Map evolves over time into a community-built 3D environment

5. Map System Design
5.1 Base Map
Initially empty, stylized grey terrain/world
No default buildings or landmarks
5.2 Layered Construction
Each group has a separate layer of:
Buildings (user-generated)
Scanned storefronts
Shared spatial data
5.3 Visualization Rules
Only processed, approved models appear
Each object is tied to a real-world coordinate

6. Social / Collaborative Features
6.1 Group Activity
See recent additions by members
Track map growth over time
6.2 Contributions Feed
Log of:
Who added what
Where it was added
When it was added
6.3 Discovery Within Group
Navigate through a “living map” of contributed places

7. Content Boundaries
7.1 Privacy Isolation
Each group map is fully separate
No cross-group visibility
7.2 Moderation Concept (High-Level)
Ensure uploaded scans are:
Real-world valid
Properly aligned to locations
Not duplicated excessively

8. Data Model (Conceptual)
User
Group
Membership
Location Pin
Media Submission (image/video)
Generated 3D Model
Map Object (linked model + coordinates)

9. Expansion Ideas (Optional Future Layers)
Time-based evolution of maps (historical layers)
Ratings or tagging of locations
Reputation system for contributors
Shared public maps (outside private groups)
Indoor mapping (stores, malls, campuses)

10. Core Product Idea Summary
A socially built 3D world, where real locations are continuously reconstructed and shared inside private groups, turning everyday exploration into a collaborative mapping experience.