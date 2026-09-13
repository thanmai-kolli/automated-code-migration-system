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

// eslint-disable-next-line react-refresh/only-export-components -- hook lives with its context; HMR cost is negligible here
export function useMigration() {
  return useContext(MigrationContext);
}