// Mirrors supabase/migrations/*. Once a Supabase project is linked, regenerate
// with `npm run db:types` and this file is replaced by the generated one.

export type Json = string | number | boolean | null | { [key: string]: Json | undefined } | Json[];

type Timestamps = { created_at: string };

export type Database = {
  public: {
    Tables: {
      organizations: {
        Row: Timestamps & {
          id: string;
          name: string;
          plan_type: Database["public"]["Enums"]["plan_type"];
          seat_count: number;
        };
        Insert: {
          id?: string;
          name: string;
          plan_type?: Database["public"]["Enums"]["plan_type"];
          seat_count?: number;
          created_at?: string;
        };
        Update: Partial<Database["public"]["Tables"]["organizations"]["Insert"]>;
        Relationships: [];
      };
      users: {
        Row: Timestamps & {
          id: string;
          organization_id: string;
          name: string | null;
          email: string;
          role: Database["public"]["Enums"]["user_role"];
        };
        Insert: {
          id: string;
          organization_id: string;
          name?: string | null;
          email: string;
          role?: Database["public"]["Enums"]["user_role"];
          created_at?: string;
        };
        Update: Partial<Database["public"]["Tables"]["users"]["Insert"]>;
        Relationships: [
          {
            foreignKeyName: "users_organization_id_fkey";
            columns: ["organization_id"];
            isOneToOne: false;
            referencedRelation: "organizations";
            referencedColumns: ["id"];
          },
        ];
      };
      tracks: {
        Row: Timestamps & {
          id: string;
          organization_id: string | null;
          title: string;
          description: string | null;
          target_field: string;
        };
        Insert: {
          id?: string;
          organization_id?: string | null;
          title: string;
          description?: string | null;
          target_field?: string;
          created_at?: string;
        };
        Update: Partial<Database["public"]["Tables"]["tracks"]["Insert"]>;
        Relationships: [];
      };
      modules: {
        Row: Timestamps & {
          id: string;
          track_id: string;
          order_index: number;
          title: string;
          estimated_minutes: number;
        };
        Insert: {
          id?: string;
          track_id: string;
          order_index: number;
          title: string;
          estimated_minutes?: number;
          created_at?: string;
        };
        Update: Partial<Database["public"]["Tables"]["modules"]["Insert"]>;
        Relationships: [
          {
            foreignKeyName: "modules_track_id_fkey";
            columns: ["track_id"];
            isOneToOne: false;
            referencedRelation: "tracks";
            referencedColumns: ["id"];
          },
        ];
      };
      lessons: {
        Row: Timestamps & {
          id: string;
          module_id: string;
          order_index: number;
          title: string;
          type: Database["public"]["Enums"]["lesson_type"];
          content_url: string | null;
          content_json: Json | null;
        };
        Insert: {
          id?: string;
          module_id: string;
          order_index: number;
          title: string;
          type: Database["public"]["Enums"]["lesson_type"];
          content_url?: string | null;
          content_json?: Json | null;
          created_at?: string;
        };
        Update: Partial<Database["public"]["Tables"]["lessons"]["Insert"]>;
        Relationships: [
          {
            foreignKeyName: "lessons_module_id_fkey";
            columns: ["module_id"];
            isOneToOne: false;
            referencedRelation: "modules";
            referencedColumns: ["id"];
          },
        ];
      };
      quiz_questions: {
        // correct_answer is absent on purpose: learners are not granted it.
        // Server code that grades answers reads it with the service role.
        Row: Timestamps & {
          id: string;
          lesson_id: string;
          order_index: number;
          question_text: string;
          question_type: Database["public"]["Enums"]["question_type"];
          options_json: Json | null;
        };
        Insert: {
          id?: string;
          lesson_id: string;
          order_index?: number;
          question_text: string;
          question_type: Database["public"]["Enums"]["question_type"];
          options_json?: Json | null;
          correct_answer: string;
          created_at?: string;
        };
        Update: Partial<Database["public"]["Tables"]["quiz_questions"]["Insert"]>;
        Relationships: [];
      };
      user_progress: {
        Row: Timestamps & {
          id: string;
          user_id: string;
          organization_id: string;
          lesson_id: string;
          status: Database["public"]["Enums"]["progress_status"];
          score: number | null;
          completed_at: string | null;
          updated_at: string;
        };
        Insert: {
          user_id: string;
          lesson_id: string;
          status?: Database["public"]["Enums"]["progress_status"];
          completed_at?: string | null;
        };
        Update: {
          status?: Database["public"]["Enums"]["progress_status"];
          completed_at?: string | null;
        };
        Relationships: [];
      };
      certificates: {
        Row: {
          id: string;
          user_id: string;
          organization_id: string;
          track_id: string;
          issued_at: string;
          certificate_url: string | null;
        };
        Insert: never;
        Update: never;
        Relationships: [];
      };
      tutor_conversations: {
        Row: Timestamps & {
          id: string;
          user_id: string;
          organization_id: string;
          lesson_id: string;
          messages_json: Json;
          updated_at: string;
        };
        Insert: {
          user_id: string;
          lesson_id: string;
          messages_json?: Json;
        };
        Update: {
          messages_json?: Json;
        };
        Relationships: [];
      };
      org_invitations: {
        Row: Timestamps & {
          id: string;
          organization_id: string;
          email: string;
          role: Database["public"]["Enums"]["user_role"];
          invited_by: string | null;
          accepted_at: string | null;
        };
        Insert: {
          organization_id: string;
          email: string;
          role?: Database["public"]["Enums"]["user_role"];
        };
        Update: never;
        Relationships: [];
      };
    };
    Views: { [_ in never]: never };
    Functions: { [_ in never]: never };
    Enums: {
      plan_type: "individual" | "team" | "enterprise";
      user_role: "learner" | "org_admin" | "super_admin";
      lesson_type: "video" | "walkthrough" | "slide" | "quiz" | "exercise";
      question_type: "multiple_choice" | "open_ended";
      progress_status: "not_started" | "in_progress" | "complete";
    };
    CompositeTypes: { [_ in never]: never };
  };
};

export type Tables<T extends keyof Database["public"]["Tables"]> =
  Database["public"]["Tables"][T]["Row"];
export type Enums<T extends keyof Database["public"]["Enums"]> = Database["public"]["Enums"][T];
