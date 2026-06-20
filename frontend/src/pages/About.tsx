import { ReactNode } from "react";

type Feature = {
  title: string;
  description: string;
};

const CONTRIBUTION_STEPS: Feature[] = [
  {
    title: "1. Pin the location",
    description:
      "Drop a pin on a real-world storefront or landmark directly on the map.",
  },
  {
    title: "2. Capture the scan",
    description:
      "Upload three angled photos (left, center, right) or a ~5 second horizontal video sweep of the storefront.",
  },
  {
    title: "3. Submit & generate",
    description:
      "Your media is tied to its GPS coordinates, group, and your account, then reconstructed into a 3D model placed on the map.",
  },
];

const GROUP_FEATURES: Feature[] = [
  {
    title: "Private group worlds",
    description:
      "Like Life360 circles, each group owns an isolated map instance. Content stays visible only to members.",
  },
  {
    title: "Member contributions",
    description:
      "Members add new locations and explore everything the group has mapped so far. Non-members see nothing.",
  },
  {
    title: "A living, evolving map",
    description:
      "Every approved scan appears immediately, so the world grows in real time as members explore.",
  },
];

const FUTURE_IDEAS = [
  "Time-based historical map layers",
  "Ratings and tagging of locations",
  "Reputation system for contributors",
  "Shared public maps beyond private groups",
  "Indoor mapping for stores, malls, and campuses",
];

function Section({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-xl bg-white p-8 shadow-lg">
      <h2 className="mb-4 text-2xl font-bold text-gray-900">{title}</h2>
      {children}
    </section>
  );
}

function FeatureCard({ title, description }: Feature) {
  return (
    <div className="rounded-lg border border-gray-100 bg-gray-50 p-5">
      <h3 className="mb-2 font-semibold text-gray-900">{title}</h3>
      <p className="text-sm text-gray-600">{description}</p>
    </div>
  );
}

function About() {
  return (
    <div className="min-h-screen overflow-y-auto bg-gray-100">
      <div className="mx-auto max-w-4xl px-6 py-12">
        <header className="mb-10 text-center">
          <h1 className="mb-4 text-4xl font-bold text-gray-900">
            About Map360
          </h1>
          <p className="mx-auto max-w-2xl text-lg text-gray-600">
            A socially built 3D world, where real locations are continuously
            reconstructed and shared inside private groups, turning everyday
            exploration into a collaborative mapping experience.
          </p>
        </header>

        <div className="flex flex-col gap-8">
          <Section title="The Vision">
            <p className="text-gray-600">
              Map360 is a social, collaborative mapping platform where users
              progressively build a shared 3D world by scanning real-world
              storefronts and landmarks. Each group maintains its own isolated
              version of the world map, evolving in real time as members
              contribute. You start with a blank, grey 3D world and bring it to
              life together.
            </p>
          </Section>

          <Section title="How Groups Work">
            <div className="grid gap-4 sm:grid-cols-3">
              {GROUP_FEATURES.map((feature) => (
                <FeatureCard key={feature.title} {...feature} />
              ))}
            </div>
          </Section>

          <Section title="Adding a Location">
            <div className="grid gap-4 sm:grid-cols-3">
              {CONTRIBUTION_STEPS.map((step) => (
                <FeatureCard key={step.title} {...step} />
              ))}
            </div>
          </Section>

          <Section title="Privacy & Collaboration">
            <ul className="flex flex-col gap-3 text-gray-600">
              <li>
                <span className="font-semibold text-gray-900">
                  Privacy isolation:{" "}
                </span>
                Every group map is fully separate, with no cross-group
                visibility.
              </li>
              <li>
                <span className="font-semibold text-gray-900">
                  Activity feed:{" "}
                </span>
                Track who added what, where, and when as the map grows over
                time.
              </li>
              <li>
                <span className="font-semibold text-gray-900">
                  Moderation:{" "}
                </span>
                Scans are checked to be real-world valid, properly aligned, and
                not excessively duplicated.
              </li>
            </ul>
          </Section>

          <Section title="What's Next">
            <ul className="grid list-disc gap-2 pl-5 text-gray-600 sm:grid-cols-2">
              {FUTURE_IDEAS.map((idea) => (
                <li key={idea}>{idea}</li>
              ))}
            </ul>
          </Section>
        </div>
      </div>
    </div>
  );
}

export default About;
