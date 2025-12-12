'use client';

import { BackgroundBeams } from '@/components/ui/background-beams';
import ScrapeNavbar from '@/components/ScrapeNavbar';
import ArchitectureDiagram from '@/components/ArchitectureDiagram';
import TiltedCard from '@/components/TiltedCard';
import { Github, Linkedin, Twitter } from 'lucide-react';

function ContributorOverlay({ name, role, github, linkedin, twitter }: { 
  name: string; 
  role: string;
  github?: string;
  linkedin?: string;
  twitter?: string;
}) {
  return (
    <div className="w-[300px] h-[300px] flex flex-col justify-end p-4 bg-gradient-to-t from-black/90 via-black/50 to-transparent rounded-[15px]">
      <h4 className="text-white font-bold text-xl">{name}</h4>
      <p className="text-white/70 text-sm">{role}</p>
      <div className="flex gap-3 mt-3">
        {github && (
          <a href={github} target="_blank" rel="noopener noreferrer" className="text-white/60 hover:text-accent transition-colors">
            <Github className="w-5 h-5" />
          </a>
        )}
        {linkedin && (
          <a href={linkedin} target="_blank" rel="noopener noreferrer" className="text-white/60 hover:text-accent transition-colors">
            <Linkedin className="w-5 h-5" />
          </a>
        )}
        {twitter && (
          <a href={twitter} target="_blank" rel="noopener noreferrer" className="text-white/60 hover:text-accent transition-colors">
            <Twitter className="w-5 h-5" />
          </a>
        )}
      </div>
    </div>
  );
}

export default function LearnPage() {
  return (
    <main className="relative min-h-screen">
      <BackgroundBeams className="fixed inset-0 z-0" />
      
      <div className="relative z-10">
        <ScrapeNavbar />
        
        <div className="container mx-auto px-6 py-12">
          <section className="text-center mb-20">
            <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold text-foreground mb-6">
              How VisionScrape Works
            </h1>
            <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
              An AI-powered web scraper that uses computer vision and large language models 
              to understand and extract data from any webpage visually.
            </p>
          </section>

          <section className="mb-32">
            <h2 className="text-2xl font-semibold text-foreground text-center mb-12">
              System Architecture
            </h2>
            <ArchitectureDiagram />
          </section>

          <section className="mb-20">
            <h2 className="text-2xl font-semibold text-foreground text-center mb-12">
              Contributors
            </h2>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-12">
              <TiltedCard
                imageSrc="https://ui-avatars.com/api/?name=Souvik+Nayak&size=300&background=FF9FFC&color=fff&bold=true&format=svg"
                altText="Souvik Nayak"
                captionText="Souvik Nayak - Frontend Developer"
                containerHeight="320px"
                containerWidth="300px"
                imageHeight="300px"
                imageWidth="300px"
                rotateAmplitude={12}
                scaleOnHover={1.1}
                showMobileWarning={false}
                showTooltip={true}
                displayOverlayContent={true}
                overlayContent={
                  <ContributorOverlay 
                    name="Souvik Nayak" 
                    role="Frontend Developer"
                    github="#"
                    linkedin="#"
                    twitter="#"
                  />
                }
              />
              <TiltedCard
                imageSrc="https://ui-avatars.com/api/?name=Gourab+Sen&size=300&background=06b6d4&color=fff&bold=true&format=svg"
                altText="Gourab Sen"
                captionText="Gourab Sen - Backend Developer"
                containerHeight="320px"
                containerWidth="300px"
                imageHeight="300px"
                imageWidth="300px"
                rotateAmplitude={12}
                scaleOnHover={1.1}
                showMobileWarning={false}
                showTooltip={true}
                displayOverlayContent={true}
                overlayContent={
                  <ContributorOverlay 
                    name="Gourab Sen" 
                    role="Backend Developer"
                    github="#"
                    linkedin="#"
                    twitter="#"
                  />
                }
              />
            </div>
          </section>

          <footer className="text-center py-8 border-t border-border/30">
            <p className="text-sm text-muted-foreground">
              Built with Next.js, Three.js, and AI
            </p>
          </footer>
        </div>
      </div>
    </main>
  );
}

