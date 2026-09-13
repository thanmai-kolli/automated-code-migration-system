import { createContext, useContext, useState } from "react";

const MigrationContext = createContext();

export function MigrationProvider({ children }) {
  const [migrationConfig, setMigrationConfig] = useState(null);

  return (
    <MigrationContext.Provider value={{ migrationConfig, setMigrationConfig }}>
      {children}
    </MigrationContext.Provider>
  );
}

export function useMigration() {
  return useContext(MigrationContext);
}